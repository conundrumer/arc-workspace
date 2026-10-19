# Synthesis

The step of the [build order](overview.md#build-order) after [Determination](determination.md). It builds token ids and the vocabulary, the decoder and its token mask, the prefix forms of the checks and the checks of the language that [Checker](reader.md#checker) leaves to the Python lint, the event log and the trace, entries in the result cache for parts of a body, the Python package, the wheel, and a run on Kaggle. It rests on [Token stream](../../docs/arclog/arclog.md#token-stream) and [Trace form](../../docs/arclog/arclog.md#trace-form).

The step ends when the decoder admits in full every case program of `gen/` that holds no `DEMONSTRATED` form, and one program runs on Kaggle.

## Token mask

- One automaton, `Decoder`, reads the token stream of a program. Its state is the partial program so far and the clause in progress.
- `Decoder::new(session, lib)` starts a decode over a task session.
- `admissible()` gives the token mask: the tokens that may come next. A token is in the mask when every check of [Checker](reader.md#checker) holds on the partial program with that token.
- A check's prefix form refuses at the token where a refusal can no longer be undone:
    - The grammar, the scope, a site's columns, the pose rule, the pooled and lifted reads, the reads of an `Unfold` instance, an instance's input order, the type meet and the join over branches each refuse at the token that breaks them. A meet only narrows as sites are added, and a join only widens.
    - A missing instance input, the labels that an `OR` or an `IF` exports, and the checks of a `CHOOSE` form are decided at their form's `END`, so the mask can withhold only that `END`.
    - A label whose type is still undecided, such as one that only `(= *X 0)` types, is refused by the order rule and counted as grounded only once a site gives it a type. Each relation of a decode has one clause, so a top-level `(= *X 0)` in a `RULE` or a `DET` is refused at its constraint.
- `step(token)` advances the state, and gives the tokens that the engine emits after that token: declarations, input prompts, column prompts and label echoes, as [Token stream](../../docs/arclog/arclog.md#token-stream) gives.
- The vocabulary has fixed slots: the control tokens, the lib relations and components, the proposers, the fact relations, and then one relation slot, one column slot and one label slot per index, up to a cap. The caps are the survey's maxima with headroom: in the survey, one program has at most 101 declarations and 24 columns, and one clause at most 24 labels.

## Decode interface

- At any token, the decode can ask for the rows and counts of the body so far on every example. The result cache gives them from the body's entries. The caller chooses whether to ask after each clause, each atom or each site.
- When a clause ends, the engine finds the [grid columns](../../docs/arclog/constraints.md#the-output-set) of the new relation, and reports whether the relation, read as `&output`, is consistent with the task's observed data, as [Terms for the paper](../../docs/paper-terms.md#new-terms) defines consistent. The test is the one of [Solves](cases.md#solves) for a run on Kaggle, with the [open-world candidates](cases.md#candidates) of a Kaggle run. A relation whose grid columns are undetermined, as [Grid columns](cases.md#grid-columns) gives, is not consistent.
- A relation that reads a `DET` with several candidates holds the rows of every live assignment at once, each row with the assignment it was derived under in an added column. A row derived from no such `DET` holds for every assignment, as the `nil` of the Souffle `OpenValue` column does. Where a body reads several such `DET`s, a row's assignment gives a value to each, and a join keeps the rows whose assignments agree on each `DET` that both sides read. A later atom narrows the live assignments by the rows it keeps. At a clause's end, the consistency test runs per live assignment, and the relation, read as `&output`, keeps the assignments under which it solves every train pair: those are the values that the filter of [`DET`](determination.md#det) gives a program whose `&output` it is.
- A `ONE` or a `CHOOSE` form whose rows are not all written is evaluated as its plain body, whose rows bound the rows of each of its models. No clause reads the pick before the form ends, since a clause reads only relations declared before it. At its `END`, its models enter its relation's rows as an added column, as an assignment does.
- The live assignments and models of a prefix run under a cap of 100. The cap is provisional: no determination plan of the corpus has a product over 100, and the largest count of models measured is 64, as [Determination candidates](corpus-survey.md#determination-candidates) and [Open values and constraint search](corpus-survey.md#open-values-and-constraint-search) give. A prefix that reaches the cap is stopped, and the event log records the stop, so the language model narrows the determination by a more specific body.
- A candidate whose `&output` holds more than one live assignment of a `DET` without `(ONE)`, or whose grid columns are undetermined, is not consistent, and the event log records which. A synthesized program leaves nothing open, as [Inputs](overview.md#inputs) gives. For a solver, both are errors, as [`DET`](determination.md#det) and [Grid columns](cases.md#grid-columns) give.
- The row cap of a decode is no lower than the largest part that a body of `gen/` needs: abbfd121's orbit cell pairs, 256038 rows, by [Runs](corpus-survey.md#runs). An extension of a prefix whose part reached the cap is evaluated from its own reads, as [The result cache](evaluator.md#the-result-cache) gives, since a site added to a positive atom can bring the part under the cap.
- `fork()` is cheap. The state is a persistent data structure and the cache is shared, so a beam of decodes costs the states alone.
- A batch form steps many decodes at once on the thread pool.

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
- Three layers are expected to change as the synthesis work iterates: the observations given to the language model at a step, the rendering of the trace, and the layout of the vocabulary. Each sits over the event log, and no part of the evaluator depends on it.
- A renderer is one such layer. The form of [Trace form](../../docs/arclog/arclog.md#trace-form) is one renderer. The program form is the log under the rewrites of [From trace to program](../../docs/arclog/arclog.md#from-trace-to-program). The synthesis code decides which alternatives the trace keeps and how it shows a decision, and those choices are the renderer's.

## Shipping

- maturin builds `arclog-py` as an abi3 wheel for Python 3.12 and later, which covers the local 3.12 and Kaggle's 3.13. The probe under `work/kaggle-probe/` installed such a wheel offline. The wheel ships in a Kaggle dataset.
- The notebook loads the task, runs the program, and gives at most two attempts per test input, under a deadline per candidate with cancellation.
- A decoded program carries no stored value. Its run determines each `DET` from the evidence, as every determination is, and a run in the task session of its decode reuses that session's entries.

## Known gaps

None.
