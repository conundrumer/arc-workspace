# Contracts: a feature library over a solver's tables

A solver's queries carry hypotheses, for example "the result is not empty" or "every object fills its bounding box". The feature library holds handwritten extractors that test those hypotheses on the tables a query gives. A model takes the features as input and learns how to interpret them. The readings of tables as claims or plumbing are diagnostics, not targets.

## Layers

- `features/` is the model's input. Nothing in it reads a label, a reading, or a variant.
- `dev/` is the test harness: variants, postconditions, verdicts and growth reports. It is never model input.
- `guarantees/` holds what a lib component's output guarantees by construction. The dev labeling uses it.
- `nearmiss/` holds, for each task, handwritten wrong readings of its rule, as Python functions that give a wrong output for a train pair. The relevance judgment reads them. They are never model input.

## The structure of a feature

`features/schema.py` gives each feature three coordinates:

- what it reads: `static` (the query's text, its inferred column types, and the engine's identities, flows and body IR of its tables) or `dynamic` (the rows);
- its level: per example, per assignment (pooled over the examples), or across assignments (pooled over the assignments);
- its arity: its owner table, and each other table it reads, as a parent, an ancestor at a depth, or a base table (the input grid or the train output).

`features/pool.py` lifts a feature from one level to the next. A pooling operator is a function of the set of values.

`features.base_features` gives the features of the base tables at an example: the input grid, and at a train example, the output grid and the changed cells (the output's cells whose color differs from the input's at that place). Their columns keep the lib's names.

## Conventions for a feature

- A feature keeps its value under the symmetries of the square and under a permutation of the colors. An orientation value or a color enters a feature only through a relation, such as "on one axis" or "includes the commonest input color", never by its name.
- A feature's key holds no name that the program's author chose, and depends on no order that the author wrote. A key names a column or another table by its identity (`features/identity.py`), and the feature `<token> describe` gives that column or table in given terms, as the docstring of `features/features.py` gives. A feature names a column or a table through its token, never through its name.
- A feature that reads another table names it as `<column> <relation> <table>.<column>`. `coordinates` in `features/schema.py` reads the other table's place from its description.
- A feature that reads the train output ends in a suffix of `OUTPUT_FEATURES` in `features/features.py` and of `WITH_OUTPUT` in `features/schema.py`. A feature that reads the input grid as a base table ends in a suffix of `WITH_INPUT`.
- A new feature leaves the value of every existing feature unchanged.

## Testing a feature

The variants of each task stay in `corpus/<task>.jsonl.zst`: an input variant is a mutated train input, run as a new test input, and an output variant is a train output with edited cells. Every hypothesis is tested under preconditions. A variant counts for a table where the postconditions of the tables upstream of it hold. An output variant counts only where its output is one the task could have: the solver's output on an input variant that meets the preconditions of every table on the way to the output, given as the train output of that input variant's own pair. `dev/outvariants.py TASK OUT_DIR` makes these output variants. `cache/<task>.tables.jsonl.zst` holds each variant's tables, under a digest of the variant and a digest of the solver's text (`dev/tablecache.py`). The scripts that generate variants write it, and `dev/refeature.py` reads it, so a change to the library needs no engine run.

Every JSON-lines file that a run streams is kept compressed with zstd, through `dev/jsonl.py`; a reader sees each record as soon as it is written, and a script names a file by its plain name (`x.jsonl`).

Git ignores `cache/`, `corpus/` and the run outputs under `dev/`. The scripts read them, the task files and the solvers from the main checkout, also when they run from a worktree, as `features/paths.py` gives.

1. `dev/refeature.py TASK OUT_DIR corpus/TASK.jsonl` computes every feature of every variant with the current library, from the cache where it holds the variant.
2. `dev/analyze.py TASK --post-pred`, with `CONTRACTS_OUT=OUT_DIR`, gives each table's postconditions (the hull of each feature over the task's own examples) and the variants that falsify each one while the table's preconditions hold.
3. `dev/growth.py REF_OUT_DIR TASK ...`, with `CONTRACTS_OUT=OUT_DIR`, compares two runs. For each family of new features it counts the postconditions that some variant falsifies, those whose falsifying variants match no feature of the reference run, and those that fail where every reference postcondition of the same table holds. It also counts the row changes that no feature shows.
4. `dev/contingency.py TASK ...`, with `CONTRACTS_OUT=OUT_DIR`, gives each output postcondition of each table a class under the output variants that count for the table: a prediction where one breaks it and leaves the table's rows as they were, circular where the table's rows follow the edited output, vacuous where none breaks it, and untested.
5. `dev/blind.py TASK` prints the rows behind the row changes that no feature shows.
6. `dev/corpus.py OUT_DIR TASK` writes the run's variants, with their tags, to the corpus.

Each run keeps the library it ran with as `features.snapshot.py` in its output folder, and `growth.py` reads the reference run's snapshot. A run's growth report against its reference run is `growth-vs-<reference>.txt` in its output folder. An output feature is tested on output variants only, so a hypothesis about the output's size cannot fail on these variants.

## The judgments

A query's result has four properties, in the order a search meets them:

- Confirmation: the result has signal. The `degenerate` feature marks a result with none, such as an empty table or a copy of a table that exists. It is the one hard drop.
- Novelty: the result says something that the tables before it do not say.
- Relevance: the result's claims about the train output single out that output among the outputs of plausible wrong readings of the rule.
- Value: a path from the result can still reach a solution. Only a search shows it, so the dev layer gives it no judgment.

The dev layer judges novelty and relevance with what a model does not have: the input variants and the handwritten near misses. The judgments are diagnostics. A model has only the features, and the probe tests whether a learner predicts the judgments from them. The docstring of each script gives its definition.

1. `dev/judge_worlds.py OUT_DIR K TASK ...` writes each task's input worlds: its own examples and K input variants of its corpus.
2. `dev/judge_nearmiss.py OUT_DIR TASK ...` writes each task's near-miss worlds, from `nearmiss/<task>.py`.
3. `dev/novelty.py OUT_DIR [JOBS]` and `dev/relevance.py OUT_DIR` write the judgments.
4. `dev/judgment_check.py OUT_DIR` sets the judgments against `dev/judgments.json`, which holds labels written by reading each solver before any judgment was computed.
5. `dev/judgment_probe.py OUT_DIR` runs the probe.

The first two read the engine and run under the engine runtime's python with `-I -B`. The others need only numpy, scipy and scikit-learn.
