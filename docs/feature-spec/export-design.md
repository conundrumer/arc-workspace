# Feature export: design

How the engine gives the learned model a parameterized table's features. The reader is whoever implements the export, and whoever reads its vectors. The [feature specification](feature-spec.md) defines what a feature is, and the [sample contract](../sample-build/contract.md) defines `TableVector` and the keys it stands under.

## The path

- A feature expression in `engine/arclog-encoder` is the definition. `table_vector` walks a parameterized table's generated shapes over its tables and the base tables, and the catalog is a native implementation of named kinds, checked against the definition, as a native lib element is.
- `feature-encoder candidate-lists` writes the vectors of candidate queries' parameterized tables, `vector` those of a solver's parameterized table, and `base-vectors` and `query-vectors` the rest of a state's features.
- `arclog_tables::summary` stores the older `arclog_features::vector` with each exported record, and the table's rows by reference (`arclog_tables::shape_rows`). The encoder depends on `arclog-tables`, so the call into it stands in `arclog-tables-py`, which `step_tables`, `successor_tables` and `base_tables` use.
- `CaseTables.shapes(row)` gives a `TableShapes` for the table at a row, and its `vector` gives the shape values as a `ShapeVector`. The walk runs at the first `vector` call that needs it, so a draw pays for the vectors that something reads. A session keeps each vector by its `TableHash`.
- `TableShapes.rows()` gives the table's rows as bytes, in the stored form that `atom_lists::stored_of` reads (`stored::stored_json` writes it), and `feature-encoder shapes-refresh ROWS_FILE TASK OUT [--shapes FILE] [--threads N]` walks the tables of such a file on the task's grids and writes their `shapes` records. A table's record equals `TableShapes.vector()`'s, and `engine/arclog-py/shapes_rows_check.py` checks that.
- Each walk starts on a `Walker` of its own, and the walker's bound on cells stops it. So a table's vector is a function of its rows, the task's grids and the list of shapes, whatever was walked before it.

## What the catalog takes

`catalog::pass(table, facts, out)` runs on one table.

| Input | Holds | Built |
|---|---|---|
| `TableAt` | each column's value type, whether it is a key column, and the table rows as flat cells | once per table, from the export's cells |
| `PairFacts` | what the grids of a pair give: pieces, line colors, neighborhood ids, changed cells and so on | once per pair of a task, and shared by all that pair's tables |

A test input has no output. So a kind that reads no output runs on `GridFacts` of the input alone, and a kind that reads the output has no record there.

## What a learned model reads

A learned model reads feature vectors, as [Structure of the search](structure.md#maps) gives them. Offline ranking keeps one feature vector for each candidate query and ARC example, and a learned function has a value at each of a candidate's feature vectors. Those values stay apart, since a rule has to hold at every ARC example. The feature vectors have fixed columns, so a column means one thing on every feature vector of every task. The count of ARC examples differs between tasks, so a feature vector holds one ARC example's values and no column stands for an ARC example. `model/feature_eval/gate_lists.py` builds these feature vectors.

- **Columns:** a fit fixes its list of columns from train tasks and stores the list with the learned model. Every shape that a parameterized table of a train task holds is a column, in each number its set reads.
- **Duplicate columns:** columns equal on every train feature vector are one column, named by the shortest label. A fit samples columns, and a set of duplicates would otherwise count once per member.
- **Low-support columns:** a column with an entry on fewer feature vectors than `min_data_in_leaf` stands in no fit, since one side of any split of it would hold too few feature vectors.
- **A shape's numbers:** these read a shape's greatest value. Its scope is the train ARC examples where it reads the output, and every ARC example otherwise.
    - `each`: its value at the feature vector's ARC example. So a feature vector keeps which value of one shape goes with which value of another at an ARC example. Past a shape's scope it has no entry.
    - `stable`: its value, on each of a candidate's feature vectors, where it has one value at every ARC example of its scope and that value is not the default. It states an invariant of the task, which a value at one ARC example does not state.
    - `mean`, `least` and `most`, over its scope: a reading for a fit with one feature vector per candidate, which loses that pairing.
- **Missing entries:** a missing entry takes its default. A shape with no value at any ARC example has NaN, since that differs from the default.
- **Beside the shapes,** on each of a candidate's feature vectors:
    - The query's body, with no table content.
    - What the parameterized table has against the parameterized tables its query reads and the input: its entries, its stable entries, those new to these parameterized tables, the share of its entries that each of them has, and its table row count over theirs.
    - Its count of assignments. A feature vector reads one parameterized table at one assignment.
    - Its task-wide roots.
    - Its place in the state's graph, and the state's other parameterized tables against it: each shape's least, mean and greatest over the parameterized tables its query reads, over their ancestors and over the rest.
- **What the task holds,** which is the same on every candidate's feature vector at an ARC example: the base tables' vectors, the roots of the parts with no hole, and the pair family. A ranking of a ground truth query against its one-edit mutants can use these only through their interactions with the rest, so such a test does not show what they are worth.

## How a fit stores its feature vectors

A fit's feature vectors are a normalized store. Each fact stands once, at the grain where it holds, and a feature vector has a foreign key to one record of each grain.

- A value at one ARC example stands in that feature vector's record.
- A value that every ARC example of a candidate has stands in the candidate's record. It is that shape's `stable` number and, at each ARC example of its scope, its `each` number.
- What a task holds stands in the task's record, or in the record of the task at one ARC example.

`model/feature_eval/gate_lists.py` writes these records as streamable zstd. `engine/block-boost`, whose code calls a record a block, trains on them by factorized learning, with the objective, tree growth and parameters of LightGBM's lambdarank. It keeps each entry as its bin number, in a memory-mapped file. A column that the store marks as categorical (the writer's token class and token id) keeps one bin for each value, and a split on it sends a set of values left, as LightGBM splits a categorical feature. A leaf's feature vectors add their gradients to each record, and each record's entries then add those sums to the histogram once.

## Cost

- The search computes each `TableVector` once.

## Checks

- **Against the first version:** every value of a sample of tables, by `model/feature_eval/catalog_check.py` for the catalog and `model/feature_eval/template_shapes.py` for written expressions, until the first version leaves.
- **Against the definition:** each kind that has a written expression, evaluated through the engine beside the catalog.
- **Under the group:** the transformation law and the reorder check of the [evaluation protocol](evaluation-protocol.md#checks).

## What consumers do

- A new schema version compares with no earlier one, so a fit reads the new names.
- `TableHash` and the table rows do not change, so the tables and the `RowStore` stay. A feature change writes no tables.
