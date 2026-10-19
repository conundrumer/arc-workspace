# Synthesis

The step of the [build order](overview.md#build-order) after [Determination](determination.md). It builds token ids and the vocabulary, a writer from a case program to its token stream, the decoder and its token mask, the prefix forms of the checks and the checks of the language that [Checker](reader.md#checker) leaves to the Python lint, the event log and the trace, entries in the result cache for parts of a body, the Python package, the wheel, and a run on Kaggle. It rests on [Token stream](../../docs/arclog/arclog.md#token-stream) and [Trace form](../../docs/arclog/arclog.md#trace-form).

The step ends when each of these holds, or the difference is reported as a fault, as the Principles requirement of [Requirements](overview.md#requirements) gives:

- The decoder admits in full the token stream that the writer gives each case program of `gen/` that holds no `DEMONSTRATED` form. A case program that holds a fault of its solver or of the conversion that [Determination](determination.md) names is reported as that fault.
- At the `END` of each such stream's `&output`, the consistency result equals the solves outcome of the case at the values that [Determination](determination.md) determines.
- The rows of each prefix of those streams equal the rows that the evaluator gives the prefix's sub-body.
- The concept case program of aba27056, run in the Kaggle notebook on its task with the test output held out, gives one attempt on its test input, and that attempt is the test output.

## Decode settings

- A decode reads each of these settings, and each has a default. The mask or the consistency test reads a setting, and no other part of the design depends on its value, so the synthesis work can change one with no change to the design.
    - **Proposer tokens.** The mask offers the proposers as tokens, or the program writes each determination body as clauses. Default: the mask offers them. The mask reads it.
    - **Domain proposers.** The mask offers the domain proposers of [Proposers](determination.md#proposers), or not. Default: it offers them. The mask reads it.
    - **Vocabulary caps.** The relation, column and label slots of [Token mask](#token-mask). Default: the corpus's maxima with a margin: the relations a case program declares, the outputs of its instances and `CHOOSE` forms included, as a32d8b75 declares the most, the columns of a relation, and the labels of a clause, as [Forms per solver](corpus-survey.md#forms-per-solver), [Columns](corpus-survey.md#columns) and [Bodies](corpus-survey.md#bodies) give. The margin is provisional: no decode shows how far a synthesized program goes past the corpus. The mask reads them.
    - **Candidate cap.** Default: the cap of [`DET`](determination.md#det). The consistency test reads it, at each prefix.
    - **Model cap and node cap.** Default: the caps of [The constraint module](cases.md#the-constraint-module). The consistency test reads them, at each prefix.
    - **Row cap and work cap.** Default: the caps of [Joins](evaluator.md#joins). The row cap is no lower than the largest part that a body of `gen/` needs, abbfd121's orbit cell pairs, as [Runs](corpus-survey.md#runs) gives. The consistency test reads them, at each prefix.
    - **Deadline.** Default: the Kaggle run's deadline per candidate, as [Shipping](#shipping) gives. The consistency test reads it.
- The candidates of a train pair are not a setting. A run has the candidates of its task data, as [Candidates](cases.md#candidates) gives, so a decode on Kaggle task data is open-world and a decode on the task data of this repo is closed-world.

## Token mask

- One automaton, `Decoder`, reads the token stream of a program. Its state is the partial program so far and the clause in progress.
- `Decoder::new(task, session, registry, constructions, limits)` starts a decode over a task in a task session. These are the arguments of `Evaluation` in `engine/arclog/src/eval/mod.rs` less the program and its parameter values, which a decode builds and does not store.
- `admissible()` gives the token mask: the tokens that may come next. A token is in the mask when every check of [Checker](reader.md#checker) holds on the partial program with that token.
- A check's prefix form refuses at the token where a refusal can no longer be undone:
    - The grammar, the scope, a site's columns, the pose rule, the pooled and lifted reads, the reads of an `Unfold` instance, an instance's input order, the type meet and the join over branches each refuse at the token that breaks them. A meet only narrows as sites are added, and a join only widens.
    - A missing instance input, the labels that an `OR` or an `IF` exports, and the checks of a `CHOOSE` form are decided at their form's `END`, so the mask can withhold only that `END`.
    - A label that only `(= *X 0)` types is grounded by `0`, as the grounding rule of [Negation and constraints](../../docs/arclog/arclog.md#negation-and-constraints) gives. Inside an instance input, its type is the input's column at the prompt of the head site that projects it. The order rule refuses a constraint on it only once no completion can type it `number`. Each relation of a decode has one clause, so a top-level `(= *X 0)` in a `RULE` or a `DET` is refused at its constraint.
- The mask admits `(ONE)` on a `DET`, which makes its parameter open, as [Open parameters](#open-parameters) gives. It admits `ONE` marks on a `RULE`, and the derived reading of a parameter, `(RULE &x <proposer>)`.
- The mask blocks none of the [second spellings](../../docs/arclog/arclog.md#second-spellings), since that section gives them as suggestions and not rules of the stream.
- `step(token)` advances the state, and gives the tokens that the engine emits after that token: declarations, prompts of inputs and of named clauses, column prompts and label echoes, as [Token stream](../../docs/arclog/arclog.md#token-stream) gives.
- The vocabulary has fixed slots: the control tokens, the lib relations and components, the proposers, the fact relations, and then one relation slot, one column slot and one label slot per index, up to the vocabulary caps of [Decode settings](#decode-settings). The proposer slots, and the domain proposers among them, are those that the proposer tokens and the domain proposers settings offer.

## Checks moved from the lint

The checks of `src/arclog_convert/lint.py` that move to the engine in this step are the checks of the language that [Checker](reader.md#checker) does not build in step 1, by the code the lint reports:

- `=` and `0`: `head-zero`, `zero`, `zero-site`, `eq-order`, `eq-site`, `eq-mark`, `eq-same-list`.
- Labels and marks: `mark`, `remade`, `fresh-here`.
- One clause per relation: `clause-twice`.
- Instances: `broadcast-inside`, `key-site`.
- Picks: `one`, `one-place`, `choose`, `choose-no-never`, `choose-one`, `never-reads`.
- `RIGID_DET`: `rigid`, `rigid-part`.
- Proposers: `proposer`.
- The spelling of the program form, which no token stream can break, since the stream names nothing with text: `name`, `label-clash`, `wildcard`, `elide`, `field-case`.

The checks of solver structure, of the arcdata file, of `DEMONSTRATED` and of scene files move in [Tooling](tooling.md) or stay with the lint.

## Decode interface

- At any token, the decode can ask for the rows and counts of the body so far on every example. The result cache gives them from the body's entries. The caller chooses whether to ask after each clause, each atom or each site.
- When a `RULE` clause ends, the engine finds the [grid columns](cases.md#grid-columns) of the new relation, with that relation as the search's argument, and reports whether the relation, read as `&output`, is consistent: it solves the train pairs, as [Solves](cases.md#solves) gives for the run's candidates. A `DET` relation is not tested, as [Program](../../docs/arclog/arclog.md#program) gives, and the decode ends at the first relation that is consistent, which is the program's `&output`.
- A prefix that reads a `DET` with several candidates is evaluated at every live assignment, as [Determination with no stored value](determination.md#determination-with-no-stored-value) gives. The decode adds the test at a clause's end: the consistency test runs per live assignment, and the relation, read as `&output`, keeps the assignments under which it solves every train pair. Those are the values that the filter of [`DET`](determination.md#det) gives a program whose `&output` it is.
- A `ONE` or a `CHOOSE` form whose rows are not all written is evaluated as its plain body, whose rows bound the rows of each of its models. No clause reads the pick before the form ends, since a clause reads only relations declared before it. At its `END`, its models are built as [Models](cases.md#models) gives.
- The live assignments of a prefix run under the candidate cap, its models under the model cap and the node cap, and its clauses under the row cap and the work cap of [Decode settings](#decode-settings). A prefix that reaches a cap is stopped, and the event log records the stop, so the language model narrows the determination by a more specific body.
- A search over the lattice of a clause's bodies, which removing atoms gives, can hold its variants at once, as the tagged form holds live assignments: each row of the least body, the body without its optional atoms, carries in an added column the set of optional atoms it satisfies, and it holds under each variant whose optional atoms lie in that set. The rows carry the least body's columns, which are the columns of each variant only where no optional atom binds a fresh label. The least body must be grounded, and its rows run under the row cap, as every body's do. This form is provisional: no decode has measured whether asking for many variants at once finds a solution sooner than asking for each through the result cache.
- A candidate is not consistent where a `DET` without `(ONE)` that its `&output` reads takes more than one value over the live assignments, or where its grid columns are underdetermined, and the event log records which. For a solver, both are errors, as [`DET`](determination.md#det) and [Grid columns](cases.md#grid-columns) give. A `DET` with `(ONE)` is tested as [Open parameters](#open-parameters) gives.
- An extension of a prefix whose part reached the row cap is evaluated from its own reads, as [The result cache](evaluator.md#the-result-cache) gives, since a site added to a positive atom can bring the part under the cap.
- `fork()` is cheap. The state is a persistent data structure and the cache is shared, so a beam of decodes costs the states alone.
- A batch form steps many decodes at once on the thread pool.

## Open parameters

- A `DET` with `(ONE)` in a synthesized program is an open parameter, under the readings of [Open values](cases.md#open-values) that a program with one case and no alt can hold: a `DET` whose body ends in `(ONE)`, whose models are its open values, and a `DET` by a proposer or a domain with `(ONE)`, whose open values the live assignments give.
- With several `DET`s of the second reading, the open values of each are the projection onto it of the live assignments, and the program runs over the live assignments, the joint assignments that the train pairs keep, and not over the product of the parameters' sets. A solver's open values stay one set per parameter, as [Models](cases.md#models) gives; no solver holds two open `DET`s with a body, so the joint reading differs from the product for a decoded program alone.
- The program reads as M_open over those values, as [Open parameters](../../docs/handbook/principles.md#open-parameters) gives: on an input, its output is the union of the grids its assignments give, and it is undefined where it is undefined at one of them.
- The open values are models of the case, as [Models](cases.md#models) gives, so the [grid columns](cases.md#grid-columns) of M_open are found once across the live assignments, and each assignment's grids are read at those columns. The search at each assignment alone serves the filter of [`DET`](determination.md#det).
- At a clause's end, the relation, read as `&output`, is consistent where M_open solves every train pair, as [Solves](cases.md#solves) gives for the run's candidates: under closed-world candidates the union is one candidate of the pair, and under open-world candidates it holds at most two grids, one of them the given output. On Kaggle, M_open's grids on a test input are its attempts, as [Solves](cases.md#solves) gives.
- The live assignments are evaluated already, as [Decode interface](#decode-interface) gives, so M_open over them reads their output sets and runs no evaluation of its own. M_open adds the evaluation of each live assignment on the test inputs, under the candidate cap of [Decode settings](#decode-settings).

## Factorized bodies

- A conjunction of atoms, a whole body or a part of one, has an entry in the result cache, keyed by its content. That includes partial atoms. The evaluator builds a body's join from the entries the cache already holds. So a body that differs from an evaluated one by an atom or a site reuses what the two share, and a body evaluated after each atom or each site of a decode extends the previous entry by one step.
- The cache keeps the parts of each body, so that a search that adds or removes any atom finds its entries. A part is a connected component of the body's atoms, where two atoms are connected when they share a variable. Each part has its own entry, and the body's rows are the product of its parts' rows.
- A part is a subset of the body's atoms, and not a prefix. So the same entries serve decoding, which adds each atom after the last, and a search that adds or removes any atom.
- A finished clause's entry is the entry of its whole body, whatever order built it. The join order of a run with no decode is the evaluator's, and every order gives the same rows.
- The count of a body's rows is the product of its parts' counts, and the body is empty when any part is empty. So pruning a decode on a count or on emptiness builds no product. A prune reads the positive atoms at the top level of the body and the complete forms alone, as [Programs as values](reader.md#programs-as-values) gives.
- A later atom that shares variables with several parts links them. The engine first filters each linked part by a semi-join with that atom, and then joins the rows that remain. For an acyclic body, this keeps the work within Yannakakis's bound: linear in the size of the input and the size of the output.
- The generic join of [Joins](evaluator.md#joins) does the last join from the parts' indexes.
- A negated atom whose variables lie in two parts links those parts, and it is checked when they are joined.

## Event log and trace

- The engine keeps an event log: an append-only list of records, one per step of a decode or a run, in the order of the steps.
    - In a decode, a step is one token. Its record holds the token; whether the language model or the engine emitted it; what the engine observed at that step, such as the rows and counts the caller asked for and the consistency test at a clause's end; and, where the caller attaches them, the language model's other tokens with their probabilities.
    - In a run, a step is the evaluation of one relation of one case on one input. Its record holds the row count, the models enumerated, the values determined, and a stop at a cap or a deadline.
- The trace is the event log of a decode.
- Three layers are expected to change as the synthesis work iterates: the observations given to the language model at a step, the rendering of the trace, and the layout of the vocabulary, of which the tokens of [Token stream](../../docs/arclog/arclog.md#token-stream) are the starting layout. Each sits over the event log, and no part of the evaluator depends on it.
- A renderer is one such layer. The form of [Trace form](../../docs/arclog/arclog.md#trace-form) is one renderer. The program form is the log under the rewrites of [From trace to program](../../docs/arclog/arclog.md#from-trace-to-program). The synthesis code decides which alternatives the trace keeps and how it shows a decision, and those choices are the renderer's.

## Shipping

- maturin builds `arclog-py` as an abi3 wheel for Python 3.12 and later, which covers the local 3.12 and Kaggle's 3.13. The probe under `work/kaggle-probe/` installed such a wheel offline. The wheel ships in a Kaggle dataset.
- The notebook loads the task, runs the program, and gives at most two attempts per test input, under a deadline per candidate with cancellation, the default of the deadline of [Decode settings](#decode-settings).
- A decoded program carries no stored value. Its run determines each `DET` from the evidence, as every determination is, and a run in the task session of its decode reuses that session's entries.

## Known gaps

None.
