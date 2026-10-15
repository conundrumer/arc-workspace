# Case inclusion: the decision history

What decided which models become cases in a `.dl` solver, from the first "Coverage" principle on.

## 2026-05-07 — Coverage enters (eefe6e0)

The rule on how many cases:

> Useful coverage gives one model per plausible family. The prior becomes visible from each plausible angle.

The axis along which models differ:

> At any choice node, a choice can lean toward data (flatten) or toward ops (expose). Different op compositions of the same task are also distinct models — coverage extends within op-leaning territory.

## 2026-05-18 — alt model against alt impl (849f681)

A same-model test enters, so that a re-implementation gets no case.

> Two candidates are the same model iff (a) same Consts shape — same parameters, field types, relations — and (b) same outputs for every (input × Consts-value) in that shape. Different on either → different models.

> Op compositions split the same way: re-decomposing the same property over the same Consts is an alt impl. Coverage extends within op-leaning territory only when an op composition commits to a different Consts shape.

## 2026-07-03 — the failure Coverage guards, and the evidence gate (e7bb3ba)

Coverage is named as a guard:

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
4. **2026-09-03 (69d071f).** The evidence gate is restated as a separation. The new lead: "A rival that reads the task differently gets a case. A rival whose added machinery no pair exercises gets no case." The same commit scopes subsumption to any fill of the parameterization, and adds "A variant that stands on different input structure is a different reading and gets a case; a variant that finds the same structure another way is a pin."
5. **2026-09-03 (69d071f).** No relational form. "A claim with no relational form gets no case: when its encoding rests on arithmetic and the lib addition protocol closes the primitive, the claim goes with it."

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

## 2026-09-15 — the theory overhaul removes Coverage (fbd9023)

The commit message states it: "Principles: the generator theory replaces coverage by subsumption. A case stands unless it fails Fit, Fidelity, or Equivalence."

The whole Coverage section is deleted. A Cases section replaces it:

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

So the judgment gates are replaced by a grading of each branch.

## 2026-09-17 — a peer that meets the case conditions is not dropped (5eb0934)

1. A create pass on 9aec4887 reported: "Two peers meet that letter and I left them out … because I judge that no person forms them from these pairs. If plausibility of the model is a gate, the section needs the sentence; if it is not, both are cases and the solver is short by two."
2. The user ruled on the merits (02:04Z): "i saw StoredTies and FullRuns. they're out there but i would think of that when thinking of variations of the task. […] i wouldn't from these pairs, but i would if i thought more generally".
3. A first fix added a **Variations** rule: "A branch that a person forms from a variant task alone is a case. … That the pairs alone do not suggest a branch is no ground to leave it out."
4. The user asked whether the procedure line alone would do (02:28Z), then ruled (02:29Z): "do not drop a peer for any raeson if it passes". The Variations rule was reverted, and procedure.md kept one line: "Do not drop a peer that meets the case conditions, for any reason."

## 2026-09-18 — a witness needs the concept case defined (2ba3d0b)

A finalize pass on 9aec4887 asked whether an input where the concept case is undefined and a peer gives a grid is a divergence. The user saw the consequence (03:29Z):

> "there exists a witness input that diverges for two models, and the main case is undefined? allowing that to be the case, i think makes it possible to make any case you want bc you can make any task you want as long as you can find two cases under that task that diverges"

And again (03:35Z):

> "we can invent contrived models by tacking on rules? which is actually whats happening here?"

The session agreed and named the mechanism: any rule that is inert under the scene claims can be tacked on, and it yields a fitting, non-equivalent model. The user ruled "1. amend" (03:36Z). Two definitions in principles.md were narrowed:

> - **divergence witness**: an input on which the concept case is defined and …
> - Two models … are equivalent when they give the same output for every assignment and every input on which the concept case is defined.

This is the bound on the unbounded-peer construction as of 2026-09-18. It closes the construction when the base model is the concept case.

## 2026-09-18 — "drop" becomes "omit from the solver"

A finalize agent read the Drops rule as a rule about the review, not about solver membership (session 91c7364a, 13:30Z). Its own words:

> "I read 'Drops' as a rule about what the review must list, not about solver membership."

The user (13:34Z): "what if we just chose a more precise/conventional word than 'drop'". Then the user wrote the line himself (13:37Z):

> "- If a peer meets the case conditions, do not omit from the solver."

It was written with "for any reason" restored:

> If a peer meets the case conditions, do not omit it from the solver for any reason.

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

## 2026-09-21 — the goal names Concept and Coverage (da30cfe)

The Principles goal is restated as two ordered aims:

> - The goal is for the corpus to take as much as it can from each task, in this order:
>     - **Concept.** The solver expresses the task as a person sees it, as closely as possible.
>     - **Coverage.** The solver also expresses alternative ways to see the task, for the diversity of ways of writing a solver.

This is the first time since fbd9023 that the word "Coverage" names a goal rather than a deleted section.

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

### The scene-claim line added under Equivalence

Four console passes argued that a peer whose divergence lies off the scene claims is not a separate claim.

1. **9f41bd9c create**, callout 6: "I read the Cases Equivalence condition more loosely than its text. Bounding the scrape by the tips that touch the ground and bounding it by the comb's lowest line are not equivalent — a comb floating one line above the ground separates them … I treated them as one claim stated two ways, since scene claim `comb` reconciles them; the tighter reading makes the peer a second branch."
2. **9f41bd9c refine**: "My earlier handoff had dropped three peers on one reason — they part from the concept case only off the scene. That reason is void, so `Below`, `Cast`, and `Lowest` all went in as branches."
3. **9f5f939b create**, callout 2: "The handbook gives no rule for a peer model whose divergence from the concept shows only on inputs that break a scene claim, and I spent most of the pass on it. The `Sight` choice point exists only because the Equivalence condition ranges over every input on which the concept case is defined, so a redundant-under-the-scene-claim test is formally a case; by that letter, the center-is-blank and arm-is-exactly-two tests are cases too, and I left them out."
4. **9f5f939b refine**, callout 3: "By the letter of the Equivalence condition, `Clear` is a case and so are the centre-is-blank and arm-is-exactly-two tests; I included the first and excluded the others on the ground that a case must be a way of seeing the task, and the principles do not state that test."

The user's ruling (13:49Z): "i mean, i dont want agents arguing with the docs. yes the handbook answers it but can we make it more explicit?"

The line added under Equivalence:

> - Agreement on every input the generator produces does not establish equivalence either: the comparison ranges over every input on which the concept case is defined, whether or not the input breaks a scene claim.
>     - 00dbd492
>         - The two readings of an object's empty region part only where the outline is broken, an input the generator never produces, and each reading is a case.

### Judgment is not grounds for omitting a case

procedure.md Develop step 3 gains:

> - If you find a model that meets the case conditions, add it.
>     - Your own judgment or taste is not grounds for omitting it.

This restates the 2026-09-17 ruling ("do not drop a peer for any raeson if it passes").

### Fidelity as a case condition becomes Relational form

The third case condition was "**Fidelity.** The model has an encoding allowed by Fidelity." It becomes:

> - **Relational form.** Each claim the case's branches replace or add has a relational form.

The Necessity rule in lib-protocol.md loses "Remove the case whose hypothesis has no relational form without that comp."

This edit came from 9ddd00f0 refine, which used `@approximated` on a branch. The user (02:41Z): "i remember a past discussion where we decided to allow it bc it was theoretically possible that the approximation only applied to a branch and the solver could not do with out it. but wdyt", then (02:49Z) "not sure we're on same page. how about this: under your proposal, would this be possible?", then (02:50Z) "ok i agree with you. propose edits".

### The runner holds cases the solver does not write

`@derive` and `@store` directives enter solver-file.md. The runner holds the derived or stored reading of a parameter as a case, and the solver writes no branch for it. `@ignore: derive` and `@ignore: store` dismiss one.

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

## 2026-09-22 — the guard rule is set aside for a bound on where cases come from

The session had proposed a guard rule: a branch whose clauses are the concept branch's with body atoms added or removed, each added atom over a relation the concept branch reads, and whose every witness carries `@relaxed`, gets no case. The user said "go" to a check of that rule over the approved corpus.

The check applied the guard test to every non-concept branch of the approved solvers. It flagged four branches, and the user had kept each of them:

- 2d0172a1's `Nest`, the branch behind the 2026-09-18 ruling "they're out there but i would think of that when thinking of variations of the task".
- 9bbf930d's `Channel`, `Exit`, and `Mouth`, the weaker readings of `pipes` that raised the open-ended lattice on 2026-09-18.

A test on the form of a branch thus failed the same test as Exercised: it removed cases that the corpus held. In the record, what separated the kept branches from the unwanted ones was their origin. `Nest`, 9f5f939b's `Clear`, and the three pipe readings came from the task, from a variation a person imagines, or from the reference solver. The blank-center and two-cell-arm tests of 9f5f939b came from a session that enumerated the tests of its own program: "an2.py runs all eight combinations of those tests".

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

Seven Analyze sessions ran on 9f669b64, 9f8de559, a04b2602, and a096bf4d. The first three tasks each ran under two briefs: one that asked for the models as `@scene`, `@rule`, and `@claim` lines, and one that asked for no form. a096bf4d ran under the free brief with the reference TS solver left out.

The results:

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

At 23:07Z the session proposed a line under the concept case, the reach line:

> - **concept case**: the case whose model the concept statement describes.
>     - At every assignment, its model is defined on every input the generator produces.
>     - An output the concept statement leaves undetermined on such an input is a choice point or an open parameter.

The user approved (23:37Z):

> "if you really judge these to be the best resolutions hten approve
>
> besides 4
>
> here's my proposal: for the parts that should be "gated" away, defer it into a file the agent reads. then step 3 will be : Only after you have completed step 2, read X.md for the next steps"

Analyze was split at a gate: the agent reads the later steps, including the reference solver, only after it has written the concept.

### a04b2602, and the concept slot

a04b2602 ran at 00:28Z, and again cleanly at 00:59Z after a run that read an earlier run's files. Both reached the same three fitting models as the briefed free run of 18:07Z, with the concept written before the reference solver was read.

The clean run found an input where the concept and every peer agree and a person reads another output, and the steps had no place for it. The user (01:44Z): "slot: wdyt, wrt create agent and overall analysis", then (01:50Z) "ok add the concept slot". The first bullet of the gated step 3 became:

> - The concept case's model: each divergence witness against it, with the items below, where the second output is the judged output.

## 2026-09-22 — the diagnosis

The user, at 2026-09-23T02:12Z:

> "are you in bug patch mode? is this a symptom of a deper problem? consider reframing or quetsioning the premise"

The session's answer: the reach line and the three clauses added after it were four edits aimed at one behavior. Each asked the agent to state a judgment, and none changed which models became cases. A run on a251c730 showed it: it graded overlapping stamps `borderline`, and nothing followed from the grade.

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
6. The reach line goes.

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

## 2026-09-23 — every input, and branches in place of models

The session had asked whether a witness input's plausibility may decide case membership, or whether any model that differs from another anywhere is a distinct reading, with the 2026-09-18 bound dropped. The user chose the second (02:33Z): "2". Then (02:38Z) "well double check your proposal. ultrathink", and (02:47Z) "go".

The edits:

- Agree ranges over every input: "Two assignments agree when, on every input, the two models give the same output or neither is defined." `G_C` goes.
- The divergence witness loses "on which the concept case is defined". Its first bullet becomes "at some assignment, two models give different outputs, or one is defined and the other is not."
- The reach line goes.

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

### A constructor denotes only its branch's reading

On a solver that works but has a constructor named for a reading another branch shares (a25697e4), the user (15:07Z): "opt1". solver-file.md now reads: "A constructor denotes only its branch's reading, not a reading another branch shares, and is named for its branch".

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

The session answered yes.

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

## 2026-09-25 — Subsumption at the parameters either model reads

Item 2 asked at what assignment Subsumption compares two models that read different parameters. The example was a09f6c25. Its `SizeBound` branch reads the open parameter `noise_size`, and `MinSizeNoise` computes the smallest size. `store` proposed `MinSizeNoise` with the size stored as 1. The solver's `@ignore low: store` line dismissed that model as `SizeBound` at the bound 1, and a Refine pass could not judge the line.

The document then recorded as settled: the comparison is at one assignment, the witness's (the 2026-09-23 rulings); and the form in which each assignment of one model may be matched by some assignment of the other is the reparameterization exception the 2026-09-09 ruling removed. What stayed open was what that assignment gives a parameter only one model reads. Under option 1, the assignment covers every parameter either model reads. A witness that reassigns `noise_size` to 3 then shows the stored-size model differing from `SizeBound`, and the model stays as a case.

The user (21:55Z): "so item 2, it sounds like there's no good defense for opt2?" The session's answer: option 2's one argument is that it removes contrived cases, the 2026-09-18 worry "we can invent contrived models by tacking on rules?", and the 2026-09-23 ruling had answered it with "a big starting point" and "a mechanical check". Item 2 was marked settled on option 1.

principles.md now reads:

> - A model is subsumed by another when the two are not equivalent and, at every assignment of the parameters either reads, on every input where it is defined, its output is the other's.

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

### `@ignore` records a judgment

The session had ruled that the runner stops honoring `@ignore` on a lint hint. It then reversed that on its own: the runner keeps honoring it, and the `@ignore` directive would gain "or a hint". The user (2026-09-27T12:16Z):

> "What’s the difference between hints and findings? Send agent to determine how it’s actually used. Bc point of ignore is to silence what was already judged to be false flag, not to just bypass lint"

This settled the purpose of an `@ignore` line: it silences a flag that was already judged, and it does not bypass lint.

### Approved solvers outside the loop

The audits of approved solvers that have no Analyze files now reported missing `@derive` and `@store` lines, and the session planned to ask how such solvers are brought to the current standard. The user (2026-09-27T14:20Z):

> "4 out of scope"

This settled that approved solvers with no Analyze files are not brought to the current standard.

## 2026-09-28 — the user's rulings

Each ruling is given in the user's words, with what it settled.

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

The first Create pass through the rewritten tool, on ac0c5833, wrote a proposal comp `CentroidDist` that served the branch `$NearestCentroid` alone; the concept case encodes the task without it. The user:

> "the fact that a case forced the creation of a proposal comp when it wasn't the concpet case"

> "i very distinctly remember "proposal comps" fka task-local comps should be removed if they [only are for coverage] or osmething like that. at least there was a rule gating their creation or asking for their removal under some condition"

The session proposed the condition in the pass's own step and a clause under the Relational form condition. The user vetoed the principles edit ("veto principles edit. it's not a principle.") and approved one sentence in the lib protocol's proposal-comp step: a proposal comp is written only where the relations need a banned form and the concept case reads them. A branch whose claim needs the form then has no set of clauses and fails Relational form as the condition already reads.

## 2026-09-30 — the cases the tool runs are the witnessed ones

The first Create pass on ac0c5833 met 616 cases, most of them combinations that no input showed defined and differing from a case with fewer branches, and the audit's deletion survey ran every one. The user asked for a bound, then for a distance from the concept with weights from the witness labels and a threshold. A study over the six solvers with the most cases showed that no label predicts such a repeat and that every weighted threshold drops a case some witness separates. The user:

> "ok we don't have to stick with any of my suggestions. you know what i want: efficiency diversity. ultrathink on the best solution"

> "approve"

This settled that the tool computes the witnessed cases from the recorded inputs, the task's and the witness file's, with no judgment and no number to set: the concept case, each branch's model, and each case that some recorded input shows defined and giving a grid no case it extends gives, less each case that takes two rejected branches, a rejected branch being one whose every verdict is `concept`. The checks, surveys and counts read the witnessed cases; the others get no finding and no run. The rule is a tool parameter, not a principle.

## 2026-10-01 — a number that counts nothing has no relational form

The third Create pass on ac0c5833 wrote the branch `$NearestCentroid`, "the marker whose empty corner is nearest, in Manhattan distance, to the centroid of the template cells", through the lib's `Excess`, `Extremes`, `ArgExtremes` and `Unanimous`. A comment in the solver equated the greatest signed count of cell-and-line pairs with the Manhattan distance to the centroid times the cell count. The branch passed Relational form as agreement, and it passed the lint and the Refine pass. A test over eight solvers then showed the same pattern in a branch over a mean and in a branch over a median. The user:

> "those centroid things are hacking in statistics as you said"

> "i guess centroid is never the concept bc humans don't compute the centroid they just see blobs and that results in using @approximated"

> "i see you didn't consider the nature of these quantities? that they're fractional?"

> "approve"

This settled that a claim that refers to a number that counts nothing the task has, such as a mean or a centroid, has no relational form, as the Relational form section of the principles now states. A branch whose claim refers to such a number fails Relational form and leaves the solver. A rule of the concept that refers to one runs under `@approximated:`. A count arranged to equal such a number is that number under another name, and it changes nothing. Picks and counts count things, and they stand: the largest, the fewest, the middle by rank, a size, a distance, a tile count, a half, a parity.

## 2026-10-12 — a case that misses a pair of the task is witnessed

Under the 2026-09-30 entry, "the cases the tool runs are the witnessed ones", a case that takes two rejected branches gets no run and no finding. With the exclusion `( Cp = $ShapeColors() ; Cc != $ColorBoxArea() )` removed from the `impl_choice` of ad3b40cf, the case `$ColorBoxArea & $LineCompetes` returns the input on train 2, and the pair run, `witness --every-case` and `grid --case` show nothing, since that case takes two rejected branches and is not witnessed. The user's ruling, as the log of ticket 10-98 records it:

> "the checks also report a Fit failure of any case on the task's pairs, from the runs witnessed() already makes; this replaces the part of the 2026-09-30 ruling that gives cases not witnessed no finding."

This settled that a case whose output on a pair's input of the task is no candidate of that pair is witnessed, whatever branches it takes, so the pair run fails the pair at that case, and `witness --every-case` reports such a dropped case as failing Fit.

## 2026-10-14 — a test pair is scored by two attempts, and open values give their union

Fit judged a test pair as it judged a train pair, by equality with the pair's candidate, and Open parameters read the model at the open values as the intersection of their outputs. On a test input where two open values gave different grids, the output was undefined, where the competition's two attempts per test output would hold both grids: a64e4611's `quorum` is open with the values 3 to 8, and its test 0 has two candidates. The user approved the coordinator's option "The capped union for open values on test inputs", then asked of the proposed text:

> "proposed text?"

> "is all this text needed?"

> "2"

The "2" picked the reading "Split the Fit definition into a train line and a test line?".

This settled that the model's output at the open values is the union of the grids each open value gives, and that a test pair fits where the output holds at most two grids, one of them in the pair's candidate, while a train pair still fits only where the output is its candidate. On a train pair, open values that give different grids leave a union that is no candidate, so the case fails Fit there as it did under the intersection. The cap of two stands in Fit alone, so it covers a tie on a test pair as well.
