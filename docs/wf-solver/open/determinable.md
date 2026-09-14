# Determinable: which parameters it binds, and where its verdict falls

Open question in `principles.md`, Coverage — Evidence, the Determinable bullet.

## The question

The bullet binds the parameters of a table hypothesis and states a consequence only at an unseen key. Definitions already gives determination over every parameter, `detᵢ(train(T), test_in(T)) = θ(T)ᵢ`, and a solver as a program, its parameters, and their determination. Three readings are open:

- whether a stored value of a non-table hypothesis that the train pairs leave open needs a determination, or stands on a witness that two assignments give different outputs
- whether the rule's verdict falls on the value or on the hypothesis, as Unseen key's does
- what the test inputs contribute: they bound a value by well-formedness, and the test outputs are held out. The runner's sweep lines say "the test refutes", and that reads the test outputs.

## The text

> - **Determinable.** The parameters of a table hypothesis must be determinable from the train pairs and test inputs. The test outputs are held out.
>     - **Unseen key.** A test key with no train entry rules out the table hypothesis.
>         - 1fad071e
>         - 3b4c2228
>     - The correct output at that unseen key is evidence that the prior is compositional.

## Candidate text

> - **Determinable.** A hypothesis's assignment comes from the train pairs and the test inputs. The test outputs are held out. Its case stands when a determination derives the value of each of its parameters, or when the parameters no determination reaches leave one output standing at each test input. A hypothesis that meets neither gets no case.
>     - A witness that two assignments diverge shows that the value is task data, and derives none.
>     - **Determination.** A determination reads the train pairs and the test inputs. A rule whose value does not depend on them derives nothing. A pick among the values that fit, by an order their type does not carry, derives nothing.
>     - **One output.** The open parameters leave one output standing at a test input when every assignment that holds the derived values, fits the train pairs, and is defined at that input agrees there with the stored assignment.
>         + ∀θ′ ∀x ∈ test_in(T). (∀i ∈ det. θ′ᵢ = θ(T)ᵢ ∧ M(θ′) ⊨ train(T) ∧ M(θ′, x)↓) ⇒ M(θ′, x) = M(θ(T), x)
>             + det — the parameters whose determination derives their value
>     - **Unseen key.** […]

The Determination sub-bullet rests on ARC types and Color: a minimum over surviving DiagDir or Color values invents an order. A minimum over surviving numbers stands where the extreme is the concept's own, as the shortest period is (97999447, 3ac3eb23, 332efdb3).

## The reading applied

The Determinable bullet binds the parameters of a table hypothesis, as it is written, and reaches no other parameter. A proposer that the determination plan reports as exact, and a value domain that the plan reports as covering the value, are the parameter's determination. A parameter the plan covers that way carries no determination relation: the value stays stored, and a note above its `.decl` says what fixes it.

- 985ae207 — `bg`. A `Determine` comp derived it from a color mode over `ex_in`, while the plan reported it covered by the `DominantColor` proposer, exact. That comp is gone and the note stands in its place.
- 97d7923e — `bg`, the same plan verdict. The solver had no `Determine` comp and no note; it now carries the note.
- 8abad3cf — `corner` and `order_axis`, each stored, read by the `$ByPlace` rule case, and covered by its value domain. Both were left bare; each now carries the note.

## Where the approved corpus stands

No approved solver changes under the candidate text. Over the 354 approved solvers, a train-fitting rival that the test pair rejects occurs in 2de01db2 (`ink`, derived by `Determine.ink`) and 681b3aeb (`bg`, `DominantColor`), both determined. 1da012fc stores a `corner` every value of which reproduces the test output, so One output carries it.

## Solvers

- 8abad3cf (draft) — `corner` and `order_axis` were cleared on witness grids. The train pairs admit `DIAG_TR` and `AXIS_H` as well, no Determine relation or proposer reaches either value, and each rival is defined at the test input and differs there. Under the candidate text `$ByPlace` gets no case, and the file keeps `$BySide` with no `Choice`, no `corner`, no `order_axis`, and no `LexOrder` or `Extremes` instance.

## Tool gap

`run_dl.py determination-plan` reports a parameter as covered by `domain enumerable(N)` with no check that one value survives.
