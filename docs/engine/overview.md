# Engine overview

What the engine does, what it must meet, and the order it is built in. Each step of the build has a scope doc that designs it.

The engine runs [arclog](../../docs/arclog/arclog.md) and [arcdata](../../docs/arclog/arcdata.md) files over the lib of [lib-spec.md](../../docs/lib-spec.md). The language is defined by those docs and by [constraints](../../docs/arclog/constraints.md) and [rigid](../../docs/arclog/rigid.md). The forms the engine shows of a program, and the decoder's reading of a few forms, are in [arclog-stream.md](arclog-stream.md) and [arclog-expansion.md](arclog-expansion.md), and the replaced Souffle forms, the evidence and the implementation of the two forms are in [constraints.md](constraints.md) and [rigid.md](rigid.md). The corpus numbers that the design rests on are in [corpus-survey.md](corpus-survey.md). The corpus is the solvers under `work/arclog/gen/`, called `gen/` in these docs.

## Uses

- **Kaggle run.** Given a task and a program, give at most two attempts per test input, offline, within the time limit.
- **Synthesis loop.** A language model decodes programs. The engine gives the tokens that may come next, prunes a decode on its prefix, tests candidate programs against the train pairs, and gives the trace of a decode. The language model's tokenizer and decoding loop are outside the engine.
- **Solver work.** Refine passes over the solvers of `gen/`: run the cases, judge whether each case solves the task, run the witnesses, determine the parameters, and report each error in the names of the solver's files.
- **Oracle check.** Give the outcomes of a solver of `gen/`, to compare with the Souffle solver it was converted from. The engine does not run `.dl` solvers.

## Requirements

These requirements are in order of priority. The order settles a conflict between two parts of the design.

1. **Principles.** The engine follows the handbook's [Principles](../../docs/handbook/principles.md). The semantics it implements are the handbook's definitions: [hypothesis, solves, split task and determination](../../docs/handbook/principles.md#models-and-tasks), where the handbook says model for hypothesis and fit for solves, as [Terms for the paper](../../docs/paper-terms.md) gives, [open values](../../docs/handbook/principles.md#choice-points-and-open-parameters) and [M_open](../../docs/handbook/principles.md#open-parameters), [witnesses](../../docs/handbook/principles.md#witnesses), [equivalence and subsumption](../../docs/handbook/principles.md#equivalence-and-subsumption), [cases and the case conditions](../../docs/handbook/principles.md#cases), and [equivariance under Γ](../../docs/handbook/principles.md#invariance). The scope docs link to these definitions and do not restate them. The engine keeps equivariance by construction, as [equivariance.md](equivariance.md) gives.
2. **Fidelity to the corpus.** Every solver of `gen/` gives the outcomes that its arcdata file records. The Souffle solvers are the test oracle until the corpus moves to arclog. Where a Souffle outcome departs from Principles, Principles rule, and the engine reports the difference as a fault of the solver or of the Souffle lib.
3. **Errors found by the engine.** The checker refuses what the language refuses. A run that disagrees with a record is reported as a fault.
4. **Speed on the corpus.** A refine pass over every solver runs no slower than on Souffle.
5. **Throughput of the synthesis loop.** Many candidate programs per second on one task, with the provisional target of [Proposals for the synthesis loop](performance.md#proposals-for-the-synthesis-loop). The candidate programs on one task share cached work, such as the parse of the inputs and the lib instances over them. A program prefix is evaluated as far as it goes, so a decode is pruned early. [Synthesis](synthesis.md) builds the synthesis loop, and the steps before it keep it possible.

The engine also meets these requirements:

- **Programs as values.** The caller builds programs and edits them: add, remove or replace an atom or a site. The engine evaluates an edited program and reuses the work it shares with a program already evaluated. Token decoding is one client of these edits. Other search procedures, such as a search over the clauses that removing and adding atoms gives, stay possible and cheap, and the design commits to none of them. [Programs as values](reader.md#programs-as-values) and [The result cache](evaluator.md#the-result-cache) give how.
- **Open to iteration.** What the language model sees of a decode, and how the trace is rendered, change often. A change to either changes no other part of the engine, as [Traces](synthesis.md#traces) gives.
- **Bounds.** Work stops at caps and time limits, and a candidate program can be cancelled. A bound that is reached is an alert, since no solver and no check should reach one, except the cap on the search for a canonical labeling, which refuses the form that passes it, since the form's hash would depend on its written order: the run reports the clause or search and the bound, and the report counts as a fault to fix. In the synthesis loop, a candidate program that reaches a bound is stopped, and its trace records it, so the share of candidate programs stopped by each bound is reported.
- **Determinism.** The Idents a writer writes and the outputs are the same from run to run. No output depends on an order of the engine's encodings, as [Parallelism and determinism](evaluator.md#parallelism-and-determinism) gives.
- **Shipping.** One offline wheel on Kaggle's Python 3.13.

## Crates

- The engine is one Cargo workspace at `engine/`, with these crates:
    - `arclog`, the core: reader, resolver, writer, checker, evaluator, the algebra relations and tables, determination, judge and trace.
    - `arclog-constructions`, the lib's constructions. The core crate changes least, and a change to a construction rebuilds this crate alone.
    - `arclog-tables`, the tables of a decode step, their columns, the column flows and `solver_tables`.
    - `arclog-bindings`, a library crate with the pyo3 bindings of the streams export, which are every binding of the `arclog` module other than the tables ones.
    - `arclog-tables-py`, a library crate with the pyo3 bindings of the tables export, which `engine/arclog-tables-py/src/lib.rs` registers.
    - `arclog-cli`, a binary for the dev loop and the refine passes, with no Python in the path.
    - `arclog-py`, the pyo3 extension, built by maturin as an abi3 wheel. It holds the module init, which registers the names of `arclog-bindings` and `arclog-tables-py`, and `streams_digest()`.
- No crate of the streams path, which is `arclog`, `arclog-constructions` and `arclog-bindings`, depends on `arclog-tables` or `arclog-tables-py`, so the compiler refuses a call from the streams path into the tables code.
- Rust implements every part from reading a file to judging a run. The Python package `arclog` holds the bindings alone. The Kaggle notebook, the language model's decoding loop and the agents' scripts call it.
- The engine does not implement the present `Engine` protocol of `src/engine/engine.py`. The present tooling keeps running the Souffle solvers.

## Inputs

The engine reads synthesized programs, solvers, and tasks. A task is the train pairs and the test inputs that a program runs on.

- A synthesized program is a token stream, as [Token stream](../../docs/engine/arclog-stream.md#token-stream) gives. It has one case, since it holds no alt, as [Alts](../../docs/arclog/arclog.md#alts) gives, and no `DEMONSTRATED` form. It may have an open parameter, as [Open parameters](synthesis.md#open-parameters) gives. It has no arcdata file.
- A solver is read from its `.arclog` and `.arcdata` files, and never from a token stream. Each case of a solver is a program with one case, and that program has a token-stream form, as a synthesized program has.
- A scene file is not an input, as [Scenes](#scenes) gives.

## Build order

Each step is checked against the corpus and the Souffle solvers, as [verification.md](verification.md) gives. The design decisions whose cost every candidate program and every case pays are in [performance.md](performance.md). An implementation detail that a scope doc gives, such as a data structure, an algorithm or a hash, is provisional until the engine is written and a benchmark measures it. Each scope doc gives the check that ends its step.

Synthesis is built as early as it can be. The steps before [Synthesis](synthesis.md) build what a synthesized program reads, which is a program with one case and no `DEMONSTRATED` form, as [Inputs](#inputs) gives. The full run of every case comes after it, and then the step that refine needs.

1. [Reader and checker](reader.md)
2. [Evaluator and lib](evaluator.md)
3. [Cases and judge](cases.md#one-case), for one case
4. [Determination](determination.md)
5. [Synthesis](synthesis.md)
6. [Cases and judge](cases.md#every-case), the full run of every case
7. [Refine](cases.md#refine-step), the witnesses and the case conditions of the judge, and [Tooling](tooling.md)

The estimated size is 18,000 to 24,000 lines of Rust, and 1,000 to 2,000 lines of arclog for the proposers and the checks. The estimate is provisional: no measurement gives it.

## Known gaps

Each scope doc has a table of known gaps. A gap is a part of the design that the docs and the corpus do not settle.

- Each cap, bound, heuristic and estimate gives its evidence. One that has none is provisional, says so, and is set from evidence in its doc's step.

- Each step begins by reading the gaps of its doc.
- A gap is settled in its doc's step, by the corpus where the corpus can decide it.
- Each resolution goes into the scope doc where its rule lives, as the rule alone, and its gap row is removed.
- When an agent finds a gap that no table gives, it adds a row to its doc's table. It carries out a resolution that departs from no ruling of the user and no line of Principles, and brings any other resolution to the coordinator.

## Scenes

- Scene work is outside the engine's scope: running the `parse` and `RENDER` clauses of [arcscene](../../docs/arcscene.md), checking the round trip, and generating scene instances for training data.
- A scene file, `<task_id>.arcscene`, is an s-expression file that the arclog reader reads. The language model emits no scene file, so a scene file is never a token stream.
- A later scene engine can reuse the reader, the checker's rules for the forms that a scene file shares with arclog, the evaluator and the constraint module. The evaluator runs a `parse` as it runs a `DET`: a `parse` derives a declared relation's rows from the task side, and reads the arclog file's relations. Once an instance is given, it runs a `RENDER` body and a constraint as clause bodies over the scene side.
- A scene engine builds its own instance generator, the checks of the forms that only a scene file has, the round-trip check, and the comparisons of [Shared names](../../docs/arcscene.md#shared-names) and [Render](../../docs/arcscene.md#render).
- The engine keeps these properties for a scene engine:
    - A render is a clause program whose fact relations are the scene's.
    - `ex_input` can be a derived relation.
    - The interface of the constraint module gives enumeration and the first model, and a scene engine adds sampling over the same input.
- Nothing else is kept for scenes.
