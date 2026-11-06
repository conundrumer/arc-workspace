# Feature export: design

How the engine gives the model a table's features. The reader is whoever implements the export, and whoever reads its vectors. The [feature specification](feature-spec.md) defines what a feature is, and the [sample contract](../sample-build/contract.md) defines `TableVector` and the keys it stands under.

## The path

The export already computes a `TableVector` in the engine: `arclog_tables::summary` calls `arclog_features::vector` on each table at each assignment, and `columns` stores the result with each row. That path stays, and what the crate computes changes.

- `engine/arclog-features` holds the native catalog. It has no engine dependency, so the engine and `arclog-features-py` call one function.
- `names()`, `version()` and `vector()` keep their roles, and `table_feature_names` and `table_features_version` keep theirs in Python.
- A feature expression in `engine/arclog-encoder` is the definition. The catalog is an implementation of it, checked against it, as a native lib element is.

## Which tables

- Each parameterized table of the export, at each assignment, and each base table.
- For the writer, the body table in progress and each successor body table, from the decoder's rows, with no stored query. The writer's candidate block reads these, and training rows and the live writer call one function, through a binding in the site wheel.

## What the catalog takes

`catalog::pass(table, facts, out)` runs on one table at one example.

| Input | Holds | Built |
|---|---|---|
| `TableAt` | each column's value type, whether it is a key column, and the rows as flat cells | once per table at an example, from the export's cells |
| `PairFacts` | what the grids of a pair give: pieces, line colors, neighborhood ids, changed cells and so on | once per pair of a task, and shared by all that pair's tables |

So `Input` gains two fields: the key flags of the columns, and the task's `PairFacts`. The evaluator holds the facts for its task, since it holds the grids.

A test input has no output. So a kind that reads no output runs on `GridFacts` of the input alone, and a kind that reads the output has no record there.

## From records to a vector

`pass` gives a record per binding of a kind's holes. A kind's value type decides the numbers.

| `Value` | Number | At an example |
|---|---|---|
| `Bool` | 0 or 1 | greatest and sum |
| `Num(n)` | n | greatest and sum |
| `Share(hits, of)` | the fraction, reduced before it becomes a float, so equal fractions give equal floats | greatest and least |
| `Word(w)` | one categorical column per kind, whose categories are the kind's words | the multiset's words, as one value |
| `Null`, or no record | none | no value |

- **Over constraint models:** the mean within an example, as the contract gives for several TableRows.
- **Over examples:** `:min`, `:mean` and `:max`, over the train examples for a kind that reads the output, and over every example for any other.
- **Examples with a value:** a kind with no value at some example also gives `:count`, the number of examples that have one. So a kind has one value at every example where its `:min` equals its `:max` and it has no `:count`, and a consumer reads stability from the vector.

So a kind gives 6 numbers, and at most one more. These are the `TableVector`'s entries, under names that hold the kind's template, with its holes typed by value type, and the number's name.

## Layout

A vector is sparse, since most entries are at their default on most tables. It is stored as compressed rows: an offset per row, then for each entry its index into `names()` and its value as `float32`. `names()` lists every entry of one schema version once. `version()` is a hash of that list.

A consumer that needs dense columns, as the trees do, builds them for the columns it keeps, and a missing entry reads as the entry's default. A fit fixes its list of columns from train tasks and stores the list with the model. A kind with no value at a row is stored as NaN, since that differs from the default.

## Cost

- The catalog takes 80 to 115 microseconds per table at one pair, on tables of a mean of 292 rows.
- A table at one assignment on a task of 4 train pairs takes under half a millisecond.
- The state search computes each `TableVector` once, when that table is first made, as its [specification](../state-search/state-search-spec.md) gives. The export adds no cache.

## Checks

- **Against the first version:** every value of a sample of tables, by `model/feature_eval/catalog_check.py` for the catalog and `model/feature_eval/template_shapes.py` for written expressions, until the first version leaves.
- **Against the definition:** each kind that has a written expression, evaluated through the engine beside the catalog.
- **Under the group:** the transformation law and the reorder check of the [evaluation protocol](evaluation-protocol.md#checks).
- **Between callers:** the export's vector and `arclog-features-py`'s are bit-equal on a sample, as the contract requires.

## What consumers do

- A new schema version compares with no earlier one, so `samples/SET/points/` is written again, and a fit reads the new names.
- `TableHash` and the rows do not change, so the tables and the `RowStore` stay. A feature change writes no tables.

## Later steps

- Small enumerated expressions enter as more names of the same list, from `arclog-encoder`'s one-pass family, at the size that the evaluation protocol's rule sets.
- Program relations enter the `QueryVector`, and no table reads them.
