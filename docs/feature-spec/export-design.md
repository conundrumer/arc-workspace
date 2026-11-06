# Feature export: design

How the engine gives the model a table's features. The reader is whoever implements the export, and whoever reads its vectors. The [feature specification](feature-spec.md) defines what a feature is, and the [sample contract](../sample-build/contract.md) defines `TableVector` and the keys it stands under.

## The path

- A feature expression in `engine/arclog-encoder` is the definition. `table_vector` walks a table's generated shapes over its rows and the base tables, and the catalog is a native implementation of named kinds, checked against the definition, as a native lib element is.
- `feature-encoder candidate-lists` writes the vectors of a gate's tables, `vector` those of a solver's table, and `base-vectors` and `query-vectors` the rest of a state's features.
- `arclog_tables::summary` still stores the older `arclog_features::vector` with each row of the export, so nothing in the export or a search reads the encoder's features. A search needs a call into the encoder before it can read a fit's columns.

## What the catalog takes

`catalog::pass(table, facts, out)` runs on one table at one example.

| Input | Holds | Built |
|---|---|---|
| `TableAt` | each column's value type, whether it is a key column, and the rows as flat cells | once per table at an example, from the export's cells |
| `PairFacts` | what the grids of a pair give: pieces, line colors, neighborhood ids, changed cells and so on | once per pair of a task, and shared by all that pair's tables |

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

## What a model reads

A row is one candidate query at a state. A model reads a row as fixed columns, so a column means one thing on every table of every task. `model/feature_eval/gate_lists.py` builds these rows.

- **Columns:** a fit fixes its list of columns from train tasks and stores the list with the model. A shape is a column where it tells a gold query's table from a mutant's on enough train tasks.
- **Equal columns:** columns equal on every train row are one column, named by the shortest label. A fit samples columns, and a set of equal columns would otherwise count once per member.
- **A shape's numbers:** these read a shape's greatest value over its scope, which is the train examples where the shape reads the output, and every example otherwise.
    - `stable`: the value, where the shape has one value at every example of its scope and that value is not the default. It states an invariant of the task, which a mean does not state.
    - `mean`, `least` and `most`: for every active shape.
- **No entry:** a missing entry reads as its default. A shape with no value at any example has NaN, since that differs from the default.
- **Beside the shapes:**
    - The query's body, with no table content.
    - What the table has against the tables its query reads and the input: its entries, its stable entries, those new to these tables, the share of its entries that each of them has, and its rows over theirs.
    - Its count of assignments. A row reads one table at one assignment.
    - The roots of the parts with no hole, which are the same on every row of a task.

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

- A new schema version compares with no earlier one, so a fit reads the new names.
- `TableHash` and the rows do not change, so the tables and the `RowStore` stay. A feature change writes no tables.
