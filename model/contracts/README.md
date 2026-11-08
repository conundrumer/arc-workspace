# Contracts: a feature library over a solver's tables

A solver's queries carry hypotheses, for example "the result is not empty" or "every object fills its bounding box". The feature library holds handwritten extractors that test those hypotheses on the tables a query gives. A model takes the features as input and learns how to interpret them. The readings of tables as claims or plumbing are diagnostics, not targets.

## Layers

- `features/` is the model's input. Nothing in it reads a label, a reading, or a variant.
- `dev/` is the test harness: variants, postconditions, verdicts and growth reports. It is never model input.
- `guarantees/` holds what a lib component's output guarantees by construction. The dev labeling uses it.
- `nearmiss/` holds, for each task, handwritten wrong readings of its rule, as Python functions that give a wrong output for a train pair. The relevance judgment reads them. They are never model input.

## The structure of a feature

A feature is a schema applied to a table. `features/grammar.py` gives the form of a schema: a name with variables for columns, and a term built from operators. A term says which items the feature ranges over (rows, values, cells, groups, boxes), what it reads of each item, what it compares that with (a grid of the example, another table, the other examples), under which equivalence relation, and how it aggregates the items. A schema gives one feature for each binding of its variables to a table's columns. `term_of` in `features/feature_terms.py` gives the term of a feature's name as a tree, which is what a model reads of a feature beside its value.

`features/schema.py` gives each feature three coordinates:

- what it reads: `static` (the query's text, its inferred column types, and the engine's identities, flows and body IR of its tables) or `dynamic` (the rows);
- its level: per example, per assignment (pooled over the examples), or across assignments (pooled over the assignments);
- its arity: its owner table, and each other table it reads, as a parent, an ancestor at a depth, or a base table (the input grid or the train output).

`features/pool.py` lifts a feature from one level to the next. A pooling operator is a function of the set of values.

`features/vocabulary.py` holds the operators that the schemas share, and `features/grids.py` what they read of a grid. The schemas are in `features/tables.py` (what a table's rows state alone), `features/upstream.py` (how they stand to the tables upstream), `features/relations.py` (pairs of cells and of objects in one row, and colored cells against the output), `features/dependencies.py` (functional dependencies), `features/outputs.py` (claims about the train output), `features/inputs.py` (claims about the input grid), `features/roles.py` (the role its colors, cells, numbers and directions play in a grid), `features/maps.py` (whether its rows map the input to the train output, and how its groups and lines are laid out), `features/values.py` (which objects and colors it takes from the tables upstream, and how its numbers and directions stand to its cells), and `features/across.py` (what holds of it across the task's examples). `features/assignments.py` gives how a table stands to the same table at the task's other retained assignments, and `features/progress.py` what it adds to the tables before it. A claim about the train output also applies at a near miss. The others apply at a task's own examples: `all_features` takes `own=False` for a variant, whose features the novelty judgment reads, and `others` for the tables at the other assignments.

`features/typed.py` is a second version of the library, which the environment variable `CONTRACTS_LIBRARY=2` turns on. A feature reads a color only through equality, so a color is one equivalence type among others, and the same schemas hold of a labeling of a grid by another type: the shape of a cell's component, up to translation or up to D4, the component itself, or its size. It also takes the type of a table's label column as a parameter, groups a column of cells by any such column, and gives a group's shape the measures that a color column has.

`features.base_features` gives the features of the base tables at an example: the input grid, and at a train example, the output grid and the changed cells (the output's cells whose color differs from the input's at that place). Their columns keep the lib's names.

## Conventions for a feature

- A feature keeps its value under the symmetries of the square and under a permutation of the colors. An orientation value or a color enters a feature only through a relation, such as "on one axis" or "includes the commonest input color", never by its name.
- A feature of an ordered pair of columns is given for both orders, so the order of a table's columns changes no key and no value.
- A feature's key holds no name that the program's author chose, and depends on no order that the author wrote. A key names a column or another table by its identity (`features/identity.py`), and the feature `<token> describe` gives that column or table in given terms, as the docstring of `features/features.py` gives. A feature names a column or a table through its token, never through its name.
- A feature that reads another table names it as `<column> <relation> <table>.<column>`. `coordinates` in `features/schema.py` reads the other table's place from its description.
- An operator states the grids it reads, as an argument or in `reads`. The lists of what reads a grid, in `features/features.py` and `features/schema.py`, follow from the terms.
- A feature's name uses conventional terms.
- A new feature leaves the value of every existing feature unchanged, other than the counts of claims in `features/progress.py`.

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

The library runs under the engine's caps and session byte bound, and reads each entry's rows as the engine holds them (`gold_tables(held_rows=True)`). A product of parts over the projection cap gives its row count and its parts, and no row of the product is built. `features.view_features` gives such a table its row count and the features of each part's rows, without those that read the whole table.

Runs retain every assignment whose tables stay within the bounds, including assignments that fail the train pairs. A query past a cap at one assignment ends that assignment, and the others stay; a dropped assignment and its reason are recorded in `tb.selection`. The surviving rows remain available through `tb.entries` and `tb.assignments`, and the per-table `assignments` count includes their retained keys. The library reads the solving assignment for a base run and a matching pinned assignment for a variant, and fails if that required assignment is absent. `Solver.tables_each` exposes the retained assignments to the dev `breaks.py` experiment.

For an OUT that reads different relations, the library joins their assignment keys before reconstructing its grid. It first looks for a key whose first model gives every primary train output. If none does, a tiebreak pair accepts its complete set of demonstrated grids without depending on native model order. A read never substitutes an incompatible assignment when the required one is unavailable.
