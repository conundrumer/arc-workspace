# Sample data: type contract

This contract gives the types of the sample data and the invariants that every implementation of the build must hold. It makes no claim about the language of a field.

## Terms

* comment: The user's words, session 12a37de8, 2026-11-06: "A table is supposed to be over just one example. And there was the constraint model thing too."
* comment: The user's words, session 12a37de8, 2026-11-06: "Always qualify or conventional terms . No more single loose words. Row is confusing".
- A **task** is one ARC task. Its **ARC examples** are its train pairs and its test inputs; each ARC example has a kind (train or test) and an index. A **test output** is the output grid of a test pair. No field of this contract is computed from a test output.
- A **ColumnValue** is a value of a column's type, such as a Color or a Position. A **table row** is a map Column → ColumnValue. A **Type** is a set of Column, where a Column is a field with a column type, with no name and no order.
- A **table** is a set of table rows of one Type: one parameterized table at one assignment, for one ARC example, under one constraint model. Example is a column of each table row, and its value is the table's ARC example. Two tables are one when they hold equal table rows.
- A **parameterized table** is a base table or an output of a query. It has one Type, fixed by its query. The **base tables** of a task are `input`, `ex_input` and `ex_output`. The lib's relations and components are operators in a body: none is a parameterized table, and none is in a state.
- A parameterized table maps each Assignment over the DETs it depends on to its **tables at that assignment**: a set of tables, one for each ARC example and each constraint model. With no factor in use, there is one table for each ARC example. The engine enumerates a parameterized table's assignments depth-first, DETs in dependency order and values in content order (see `Assignment` for its walk and its cap). The table **at** an assignment is a table of that set.
- A **constraint model** is one choice at each factor that a parameterized table uses on one ARC example, a factor being a ONE pick, the table rows of a CHOOSE, an open parameter, a DEMONSTRATED key or an Unfold tie. It is local to the parameterized table and the ARC example, with no identity across ARC examples.
- A **query** is (body, inputs, outputs):
    - A **Reference** is an atom that uses a parameterized table: in the body of a RULE, DET or OUT, in a clause at an input port of an INIT's component, or in a part of a RIGID_DET. `inputs` maps each Reference to the parameterized table it uses.
    - A **Name** is the one output of a RULE, DET or CHOOSE, an output port of an INIT's component, or a part or the pose of a RIGID_DET. An OUT has none. `outputs` maps each Name to a parameterized table.
    - A query **computes** its outputs from the parameterized tables it **uses**, which are the parameterized tables its References use. An input port and an output port are places in a body: an input port is where an INIT's input clause stands, and an output port is where an INIT's output stands.
- The **use closure** of a query is the query, the queries that compute the parameterized tables it uses, and so on down to the base tables.
- A DET has one or more values. Each value is a table of the DET's Type. A query **depends on** each DET in its use closure, and each of its parameterized tables depends on the same DETs. A DET is in its own use closure, so a DET's parameterized table depends on that DET. A **dependent query** of a DET is a query that depends on it.
- An **Assignment** over a set of DETs maps each DET to one of its values.
- Every parameterized table has its full set of tables at every assignment. There is no cap on table rows and no count-only table.
- A **relabelling** of a query renames its variables, its own label, the labels of the parameterized tables it uses and the field names of computed parameterized tables, with no other change.
- A **state** is a set of queries, closed under inputs (see `State`). A **member** of a state is a query in that set.
- A **program** is a set of queries closed under inputs, with one OUT. It holds at most one query per `QueryHash`, choice queries (DET, ONE, CHOOSE) included, so two DETs with one body are one parameter. A **partial program** has no OUT.
- A program **solves** a task when, over the assignments at which its train outputs equal the given ones, and within each over the constraint models of the OUT, the distinct test grids number at most two, one of them the answer.
- The **union graph** of a task holds every case's queries. A parameterized table of one query stands for one of another where their maps Assignment → `TableHash` are equal, DETs of different `QueryHash` being paired by equal sets of their values' `TableHash`es. It is a measurement. A graph query is a query of the union graph, and it is **applicable** at a state when every parameterized table it uses is in the state.
- The **writer** is the component that writes one query from a state. Its **learned model**, a set of trees or a neural network, scores the tokens the engine admits. The writer writes a query, never an assignment.
- A **feature vector** is the one input vector that a learned model reads. [Structure of the search](../feature-spec/structure.md#maps) gives its content.
- A **training instance** is one feature vector with its label, as a fit reads it. [Training instances](training-instances.md) gives the writer's.
- A **fit** is any step that sets, from data, the parameters of the learned model or of another learned function, or a statistic that one of them uses.
- An **experimental condition** is one setting of a run that a measurement compares. An **engine build** is the engine and its bindings built from one commit. A **patched code version** is a copy of the search and writer code with changes that a run imports. A **sampled query** is a query that the search's writer wrote in a run.
- Other words stand for these and are not used: definition, function, form, clause and line (for a query); node (for a parameterized table); world (for an assignment); walk (for a state sequence); given table (for a base table); row (for a training instance, a feature vector or an entry of a summary); arm (for an experimental condition); site (for an engine build); overlay (for a patched code version); draw (for a sampled query); and a bare row, point, model or example. A code name stands in text only where it names that code.

## Levels

A feature's value stands at one level, and a level above it combines the values of the level below over one index.

| Level | Index | What it holds |
|---|---|---|
| 1. A feature's value | one table | a feature expression's value on one table |
| 2. Over constraint models | the constraint models of one ARC example, at one assignment | the mean within the ARC example |
| 3. Over ARC examples (`TableVector`) | the ARC examples, at one assignment | the values of level 2 stay apart, and offline ranking keeps one feature vector for each ARC example. The numbers across ARC examples are `stable`, `least`, `mean` and `most`, which a learned model reads as columns of its feature vector |
| 4. Over assignments (`AssignmentVector`) | the assignments of one parameterized table | the count of assignments, `capped`, `distinct`, `differ`, and the assignment min, assignment mean and assignment max of each entry |
| 5. Query (`QueryVector`) | the tables a query uses and computes | the query's own features |
| 6. State features | any parameterized tables of a state | [State features](../feature-spec/feature-spec.md#state-features) |

- Level 2 comes first because a constraint model has no identity across ARC examples.
- `least`, `mean` and `most` are taken over an entry's scope: the train ARC examples where the entry reads the output, and every ARC example otherwise. `stable` is an entry's value where it has one value at every ARC example of its scope and that value is not the default.
- The assignment min, assignment mean and assignment max are taken over the assignments of a parameterized table. Code writes them as the suffixes `:min`, `:mean` and `:max` (`assignment_vector_names()` in `model/study/sampler/writer.py` and the `delta:` columns of [Training instances](training-instances.md)), and those suffixes mean over assignments wherever they stand.

## Primitive types

| Type | Meaning | Type | Invariants |
|---|---|---|---|
| `TaskId` | a task's id | string | |
| `SplitName` | a split | one of `train`, `dev`, `held-out` | |
| `BaseName` | a base table | one of `input`, `ex_input`, `ex_output` | |
| `Name` | an output of a query | string | for an INIT output, the port's name in `engine/lib/registry.sexpr`; for a RIGID_DET, `slot <n>`, n the part's position in the form's canonical form (`slot <n>.<port>` for a part that reads an instance output), or `pose`; for a RULE, DET or CHOOSE, the empty string, for its one output |
| `QueryKind` | a query's kind | one of `DET`, `INIT`, `RULE`, `CHOOSE`, `RIGID_DET` | `OUT` is not a value: OUT queries are not target queries |

## `ParameterizedTable`

How a stored field writes a parameterized table. It holds no assignment.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `query` | the query that computes it | optional `QueryHash` | absent exactly when the parameterized table is a base table |
| `name` | its output | string | a `Name` of `query`; for a base table, its `BaseName` |

- Two `ParameterizedTable`s are one parameterized table when their `query` and `name` are equal.
- Where a stored record, a vector or the export needs a key for a parameterized table at an assignment, the key is (`ParameterizedTable`, `Assignment`).

## `Assignment`

The key of a parameterized table at an assignment: an Assignment over the DETs the parameterized table depends on, a sorted tuple of (DET `QueryHash`, value hash). The DET `QueryHash` is the DET's own `QueryHash`, the one a state holds as a member.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `pairs` | each DET the parameterized table depends on, with its value | list of (`QueryHash`, value hash) | one pair for each DET the parameterized table depends on; sorted by `QueryHash` value; empty exactly when the parameterized table depends on no DET |

- A value is written as its **value hash**: a hash of the DET's own full table at that value that keeps the DET's column order, so two values that differ by a swap of two columns of one type have two value hashes. It is not the `TableHash` of the DET's parameterized table, which is free of column order. The engine's export gives it in its `assignments` part.
- Where DETs of two programs are compared, as in acceptance and in the union graph, the sets of the `TableHash`es of their values are compared, not the value hashes.
- An Assignment over a larger set of DETs gives a parameterized table the key of its restriction to the DETs it depends on. So two Assignments that agree on those DETs give it one key.
- A DET with several values has one key for each value, since it depends on itself.
- A DET's own parameterized table is fixed when the DET closes, with every top-level label of its body as a column.
- A base table depends on no DET. Its one key is the empty Assignment.
- The engine prunes a DET to the columns its readers use, and walks the pruned DET's values. It writes a dependent parameterized table evaluated at a pruned value at every full value of the DET that projects to that pruned value. So one set of tables can repeat over several Assignments.
- The cap of 256 applies to the engine's walk over the values it evaluates (the pruned values). The expansion to full values comes after the walk and has no cap, so a parameterized table can have more than 256 Assignments. `capped` means the walk stopped at 256 values.

## The tables at one assignment

The value of a parameterized table at one `Assignment`.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `types` | the column types of the parameterized table's Type, with the Ident source | list of column type | a shape's bindings depend on the Ident source |
| `tables` | its tables at that assignment | set of table | each table holds the Example column and is at one ARC example under one constraint model; equal tables are one |

- Constraint models are inside the value. They are never in a `ParameterizedTable`, an `Assignment` or a `QueryHash`.
- For each (`ParameterizedTable`, `Assignment`), the engine's export for the learned model and the state search writes the `TableVector` (see `TableVector`), the `TableHash` and table row counts: the table rows of each table and the count of tables of each ARC example. All three come from the full tables. It writes no table rows. An export for feature development also writes the `RowStore` record.
- The tables of a parameterized table are computed from a state, not stored. The stored fields that come from them are the `TableHash` and the `TableVector` of each (`ParameterizedTable`, `Assignment`).

## `TableHash`

The hash of a parameterized table's Type and its tables at one assignment, the Example column being part of each table row. The name is the code identifier. The hash covers every table of the set, so it is a hash of the set and not of one table. Opaque: a consumer compares hashes and does not decode them. It is a measurement on a parameterized table at an assignment. It is never the identity of a parameterized table or of a member of a state: two parameterized tables whose tables have equal `TableHash` are not one parameterized table.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `version` | the definition of the hash | string | two hashes compare only under one version |
| `value` | the hash | string | see below |

Properties, under one version:

- Two parameterized tables at two assignments have one hash exactly when they have equal content: equal column type multisets, and a one-to-one map of columns that keeps each type, under which the two sets of tables are equal, the Example column mapping to the Example column. A hash collision is the only exception.
- The hash does not depend on column labels, column order, table row order, the order in which the engine gives constraint models, marks, the session, the process, the machine, or the order in which the union names parameterized tables.
- The hash does not depend on a test output.
- It compares across tasks.

## `RowStore`

The tables of each parameterized table at each assignment, for feature development only. `RowStore` is the code's name for it. The engine's export writes it once per run. The export for the learned model and the state search writes no table rows.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `key` | the parameterized table at an assignment | (`ParameterizedTable`, `Assignment`) | one record for each of the parameterized table's assignments |
| `hash` | its TableHash | `TableHash` or null | null where the engine gives the table no TableHash. No other value stands for it: a table with no TableHash stands for no graph table, gives no progress, and has no `vec` of the tables file |
| `value` | its tables at that assignment (see "The tables at one assignment") | `types` and `tables` | `tables` is the full set |
| `counts` | table row counts | the table rows of each table, and the count of tables of each ARC example | |

- A change of the feature code does not write it again. A change of the engine or of the export does.

## `TableVector`

The features of one parameterized table at one assignment, keyed by (`QueryHash`, `Name`, `Assignment`), or of one base table, keyed by its `BaseName`. A parameterized table has one vector for each of its assignments. The name is the code identifier. It holds levels 1 to 3 of [Levels](#levels), not the features of one table. The engine computes it at export, from the full tables and the base tables of the task, and the learned model and the state search take it.

A feature is defined in arclog. An implementation that runs faster is checked against the definition, as a native lib element is.

The engine computes a vector by these steps (`engine/arclog-encoder/src/table_vector.rs`):

1. `table_vector` makes one instance for each (ARC example, constraint model) of the parameterized table at the assignment. An ARC example with no table gets one instance with none.
2. The walker evaluates each shape on each instance. A shape gives two numbers: the greatest and the sum of its ground expressions' values, or, for a `ratio`, the greatest and the least. A number from arclog is an integer, and a `ratio`'s value is an exact fraction, stored as two integers in lowest terms.
3. `combined` takes, at each ARC example, the mean of each number over the ARC example's instances (`mean_over_models`). A default counts as 0, and an instance with no value gives its ARC example no value. This gives a value at each ARC example, and these values stay apart.
4. The vector gives the numbers across ARC examples: `stable`, and `least`, `mean` and `most` of each number over the shape's scope, with the count of ARC examples that have a value. A default counts as its value, and an ARC example with no value counts for nothing.
5. It also gives the mean and the greatest, over ARC examples, of the count of tables of an ARC example.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `schema_version` | the definition of every feature | string | two vectors compare only under one schema version |
| `entries` | the feature values | sparse map from name to value | an entry at its default is absent; an entry with no value is stored as that, since it differs from the default |


Invariants an implementation must hold:

- No feature uses a column label, a mark, or an order: of columns, of table rows, of constraint models, of atoms, or of the queries of a program. Where a feature needs a column order, the order is a function of content.
- No feature uses a test output.
- Under a tie for the most common color, `Order`'s `maximal` output contains every tied member, so no feature takes one color of a tie.
- No feature uses the computing query: its body, kind, atom counts or depth. These go in the query's `QueryVector`.
- No feature uses the same parameterized table at another assignment, or another parameterized table of the same query.
- The vector is a function of the parameterized table's tables at that assignment and the task's base tables. So, under one schema version and one implementation, it is bit-equal across sessions, processes and machines, and two parameterized tables of one task with one `TableHash` have one vector. Where a feature uses a subset of the table rows, the subset is chosen by content.
- Each change to a feature gives a new schema version.

### Several tables per ARC example

A parameterized table at one assignment has several tables at an ARC example where it has several constraint models there. The vector handles them by these rules:

- A quantity that a feature is computed from at an ARC example (a table row count, an overlap with the train output, a color set) is computed per table and averaged over the ARC example's tables. The feature then combines over ARC examples as it defines.
- Two features are computed from the count of tables per ARC example: its mean and its greatest over ARC examples.
- So the vector has a fixed length. For a parameterized table with one table at every ARC example, each feature has the value it has on that table.
- The schema version fixes these rules, as it fixes the aggregates of the `AssignmentVector`.

## `AssignmentVector`

The features of one parameterized table across its assignments, keyed by (`QueryHash`, `Name`), or of one base table, keyed by its `BaseName`. A base table has one assignment. Each feature is computed from the parameterized table's `TableVector`s and `TableHash`es at its assignments. It is level 4 of [Levels](#levels).

| Feature | Meaning |
|---|---|
| `count` | the count of its assignments |
| `capped` | 1 when the engine's walk of the parameterized table stopped at the cap (see `Assignment`), else 0 |
| `distinct` | the count of distinct `TableHash`es over its assignments, divided by `count` |
| `differ` | 1 when its tables differ at two assignments, that is, when it has two or more distinct `TableHash`es, else 0 |
| `<f>:min`, `<f>:mean`, `<f>:max` | the assignment min, assignment mean and assignment max of each number of each `TableVector` entry `<f>` at each ARC example. An assignment where `<f>` has no entry counts its default, and one where `<f>` has no value counts for nothing |

Invariants:

- The vector is a function of the parameterized table's tables at its assignments. No feature uses the order of the assignments.
- The sample build and the policy compute it with one function, so that training and serving give one value.
- The aggregate set is part of the schema version.

## `QueryHash`

The identity of a query. Opaque.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `version` | the definition of the identity | string | two hashes compare only under one version |
| `value` | the identity | string | see below |

Properties, under one version:

- It is the engine's canonical hash of the query's resolved content (`ResolvedProgram::content`), under relabelling, order of the atoms of a body, order of the branches of an OR, and repetition of an atom in a body.
- In that content, each Reference is written as the parameterized table it uses: (`QueryHash` of its computing query, `Name`), with that `QueryHash` computed by the same rule, down to the base tables, which are written by their `BaseName`. A Reference holds no `Assignment`, because a body applies under every assignment. A key (`ParameterizedTable`, `Assignment`) adds the assignment only where a table at one assignment is meant.
- A lib operator is written as its name in the lib's registry. These names are fixed by the engine and the lib, not chosen by a query's author.
- The hash contains no other names: no label, variable name or field name of a computed parameterized table.
- Two queries have one hash exactly when they are equal under those changes and each parameterized table they use is written the same. A hash collision is the only exception.
- The hash does not depend on `*`. It depends on `^` in a key group.
- Hashes compare across tasks where the queries and their use closures are equal.
- A program holds at most one query per `QueryHash`, choice queries (DET, ONE, CHOOSE) included. So two DETs with one body are one parameter.

Notes on the engine:

- The engine's canonical form sorts the atoms of a body, except the guard and part bodies of ALL and NEVER, and keeps positional children in their order.
- The engine's hash of a query as written, with each Reference by its label, equals `QueryHash` only within one naming of the scope.

## `BaseTable`

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `name` | which base table | `BaseName` | |
| `hash` | its TableHash, as a measurement | `TableHash` | |
| `vector` | its features | `TableVector` | |

## `BuiltTable`

A member's parameterized table at one assignment, keyed by (`parameterized_table`, `assignment`). `BuiltTable` is a contract identifier: it stands for a parameterized table at an assignment and not for one table.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `parameterized_table` | the parameterized table | `ParameterizedTable` | `parameterized_table.query` is a member of the state |
| `assignment` | the key of the parameterized table at that assignment | `Assignment` | over the DETs `parameterized_table` depends on; one of its assignments |
| `hash` | its TableHash, as a measurement | `TableHash` | not an identity: two `BuiltTable`s can have one `hash`, and both stay |
| `vector` | its features | `TableVector` | equal to the vector of every other `BuiltTable` of the task with this hash |
| `inputs` | the parameterized tables that `parameterized_table.query` uses, each at its assignment | list of (`ParameterizedTable`, `Assignment`) | a base table at the empty `Assignment`, or the key of a `BuiltTable` of the state with a lower `depth`; each `Assignment` is `assignment` restricted to the DETs that parameterized table depends on; no duplicates |
| `depth` | its depth over the state's own use edges | int | 0 where `inputs` holds no member's parameterized table; else 1 + the greatest `depth` among the members' parameterized tables of `inputs`. Base tables do not count. Equal for every `BuiltTable` of one query |
| `graph_table` | the name of the graph table it stands for | optional string | a row id; no model input uses it. Present only where its `parameterized_table` stands for a graph table (see `Sample`) |

A member's `BuiltTable`s, their `hash` and `vector`, and its query's `QueryVector` are functions of the query and its use closure. They are stated once per query, and they are the same in every state that holds the member.

## `QueryVector`

The features of one query, one level above its parameterized tables: level 5 of [Levels](#levels). Each feature is computed from the query's used parameterized tables, the parameterized tables it computes, the relation between them, and the base tables of its task. One optional family is computed from the query's body. A QueryVector does not repeat a `TableVector`: a consumer takes those from the `BuiltTable`s and the `BaseTable`s.

A **used parameterized table** of a query is a `ParameterizedTable` of its `inputs`: a member's parameterized table or a base table. At one assignment of the query, a used member's parameterized table is at that assignment restricted to the DETs it depends on. Used parameterized tables are sorted with the base tables first, in the order of `BaseName`'s values, then the members' parameterized tables by (`QueryHash` value, `Name`).

A query has one QueryVector, computed over all its Names and all its assignments (see "Assignments"). The assignments of a query are the assignments of its parameterized tables. At one assignment, where a feature is computed per computed parameterized table, the value is the greatest over Names, unless the schema version defines another aggregate.

Where an ARC example has several tables (see `TableVector`, "Several tables per ARC example"), a feature over the query's parameterized table and a used one is computed per pair of tables on that ARC example (a table of the query's and a table of the used one's) and averaged over those pairs. It is then aggregated over assignments (see "Assignments").

The mean over all pairs is a known approximation:

1. The query and a parameterized table it uses can share a factor, such as a pick that both use. Then their tables on one ARC example come from joint constraint models: the query's table under one choice goes with the used parameterized table's table under the same choice.
2. A mean over all pairs then mixes choices.
3. It is still a defined measurement, and it equals the mean over the paired tables when no factor is shared.
4. The engine could give the pairing: `models_with_picks` gives each constraint model's choice at the named picks (`engine/arclog/src/eval/models.rs`). That needs an engine change.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `schema_version` | the definition of every feature, of `use_names`, of `column_origin`, and of the aggregates over assignments | string | two vectors compare only under one schema version |
| `names` | the names of the query's features | list of string | unique; the same list, in the same order, for every vector of one schema version |
| `values` | their values | list of float | same length as `names`; NaN where a feature has no value |
| `use_names` | the names of the query's features against one used parameterized table | list of string | unique; the same list, in the same order, for every vector of one schema version |
| `per_use` | for each used parameterized table, the query's features against it | list of (`ParameterizedTable`, list of float) | one item for each used parameterized table; no duplicates; in the sort order of used parameterized tables; each list has the length of `use_names`; NaN where a feature has no value |
| `column_origin` | for each `Name`, where each column of its parameterized table comes from | list of (`Name`, list of (column type, set of `ParameterizedTable`)) | one outer item for each `Name` of the query, sorted by `Name`; one inner item for each column of that parameterized table; the set is empty exactly when the column is new; inner items sorted by column type, then by the set. It is computed from the query's body and component, so it is one value for all assignments |

A column of a computed parameterized table is **carried over** from a used parameterized table when the query binds that column at a column of an atom that uses that parameterized table. It can be carried over from more than one used parameterized table. A column that is carried over from no used parameterized table is **new**. Where the query's body does not bind the columns of its parameterized table (an INIT output), the schema version defines their origin from the component.

Invariants an implementation must hold:

- No feature uses a column label, a mark, or an order: of columns, of table rows, of atoms, of the branches of an OR, of the queries of a program, of assignments, or of the used parameterized tables as the query writes them. `column_origin` and `per_use` write a used parameterized table as its `ParameterizedTable`, never by a label or by its position in the query. Where a feature needs an order, the order is a function of hashes and content.
- No feature uses a test output.
- The vector is a function of the query's `QueryHash`, the content of its used and computed parameterized tables at each of its assignments, and the task's base tables. So, under one schema version and one implementation, it is bit-equal across sessions, processes and machines.
- The family computed from the query's body is optional: a schema version holds all of it or none of it. No feature of it uses a label name.

A QueryVector is stated once per query: one `QueryHash` has one QueryVector in every state that holds it.

### Families

The features of the first three families are computed per assignment and enter as their aggregates (see "Assignments"). Features against one used parameterized table are in `per_use`. All others are in `values`.

Relation to used parameterized tables:

- the member's `depth` (the `depth` of `BuiltTable`)
- the count of the members' parameterized tables it uses
- its table row count against the greatest table row count of the members' parameterized tables it uses
- whether its Position cells are a proper subset, a proper superset of, or disjoint from those of a member's parameterized table it uses
- its table row count against that used parameterized table's, per ARC example (`per_use`)
- the share of its column types that that used parameterized table also has (`per_use`)

Column origin:

- `column_origin`
- the count of columns carried over, and of new columns
- the count of used parameterized tables from which no column is carried over

Computed from the parameterized table together with the base tables, against the used parameterized tables:

- the greatest paint or fill gain among the members' parameterized tables it uses
- its gain less that greatest gain, and whether it is greater
- the share and count of its fixed or covered cells that no member's parameterized table it uses fixes or covers
- the greatest share of cells added by the union with one member's parameterized table it uses
- its paint gain less that used parameterized table's paint gain (`per_use`)
- the share of its fixed cells that that used parameterized table does not fix (`per_use`)
- the share of its active `TableVector` entries whose value at each ARC example that used parameterized table's vector also has (`per_use`)

Computed from the query's body (optional):

- the kind, and the component: the INIT pattern or the DET operator
- the count of Names
- the counts of atoms, NOT atoms, OR branches, ORs, comparisons, ALL and IF
- the uses of base tables and of parameterized tables of queries
- the count of labels, and of labels with 2 or more sites
- the count of atoms of each lib relation

## `State`

A set of queries, closed under inputs, with the base tables. Closed under inputs means: each Reference of a member uses a base table or a parameterized table that another member computes. That set is the whole identity. Each member's parameterized tables are computed from it, with its tables at each assignment, and are not stored. The fields below that come from them are the hashes and vectors of those parameterized tables.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `id` | the state's identity | string | a hash of the sorted set of the members' `QueryHash`es |
| `members` | the members' parameterized tables, each at each of its assignments | set of `BuiltTable`, keyed by (`parameterized_table`, `assignment`) | closed under inputs; for each member, one `BuiltTable` for each `Name` and each of that parameterized table's assignments. Stored sorted by (`depth`, `parameterized_table`, `assignment`); the order serves only storage |
| `query_vectors` | each member's `QueryVector` | map of `QueryHash` to `QueryVector` | one pair for each distinct `parameterized_table.query` of `members`. Kept per query, not per `BuiltTable`, since a member has one `BuiltTable` for each `Name` and assignment and one QueryVector for all of them |
| `given` | the base tables | list of `BaseTable` | one `BaseTable` for each `BaseName`. Base tables are in every state and are not members |

Two states are equal exactly when their sets of `QueryHash` are equal. The root state has no members.

Fields over use edges (counts of parameterized tables that use a parameterized table, ancestors, the features of the parameterized tables that use a parameterized table, and whether a `BuiltTable`'s `hash` equals another member's TableHash) are functions of `State`. They are not stored. The features of a member over its own used parameterized tables are in its `QueryVector`.

## `TargetQuery`

One target query at a state: a query (body, inputs, outputs) that the writer is trained to write.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `hash` | the query's identity | `QueryHash` | not a member of the state |
| `kind` | the query's kind | `QueryKind` | |
| `hash_exact` | whether `hash` holds the properties of `QueryHash` for this query | bool | false only where an implementation cannot prove them, for example where a search for the canonical labelling stopped at its bound |
| `body` | the query's body as canonical text, for writing | optional string | present: a function of `hash`, so equal hashes have equal bodies. It writes each Reference as the `ParameterizedTable` it uses |
| `body_decodes` | whether the engine's decoder takes `body` in its written order | optional bool | present exactly when `body` is present |
| `inputs` | the parameterized tables of its References | set of `ParameterizedTable` | each is a base table or the `parameterized_table` of a `BuiltTable` of `State.members` |
| `outputs` | its Names | list of `Name` | sorted; each output's parameterized table is (`hash`, that `Name`) |
| `computes` | each of its parameterized tables at each assignment | list of (`Name`, `Assignment`) | one pair for each `Name` and each assignment of its parameterized table over the state; a parameterized table whose walk stopped at the cap is left out (see `Sample`); sorted by (`Name`, `Assignment`) |
| `computes_hashes` | the TableHash of each pair of `computes`, as a measurement | list of `TableHash` | same length and order as `computes` |
| `computes_vectors` | the features of each pair of `computes` | list of `TableVector` | same length and order as `computes`. Equal to the vector of every other parameterized table of the task with that hash. A training target value, not an input of the learned model at this state |
| `query_vector` | the query's features | `QueryVector` | computed from `inputs` and the tables of `computes`. A training target value, not an input of the learned model at this state, as `computes_vectors` |

## `Sample`

A state and its target queries. There is one sample per state.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `id` | the sample's identity | string | a hash of `task` and the state's set of `QueryHash`, so it does not depend on file order; one sample for each distinct (task, set of `QueryHash`) |
| `task` | its task | `TaskId` | |
| `split` | its task's split | `SplitName` | equal to `split` of the task's `Split` |
| `state` | the state | `State` | |
| `target_queries` | the target queries of the state | list of `TargetQuery` | distinct `hash`; sorted by `hash` |
| `target_parameterized_tables` | the parameterized tables that the target queries compute | set of `ParameterizedTable` | equal to the union over `target_queries` of (`hash`, `Name`) for each `Name` that has a pair in `computes`. Each is one unit of loss and of credit |
| `capped_target_parameterized_tables` | the count of target queries' parameterized tables left out because their walk stopped at the cap | int | a measurement; at least 0. Such a parameterized table is in no `computes` and gets no loss credit |
| `frontier_depth` | the least depth, in the ground truth graph, among the graph queries that give the target queries | int | at least 0. It is computed from the ground truth, so it serves only to group counts. No model input uses it |
| `no_progress_queries` | the count of ground truth graph queries, not members of the state, whose used parameterized tables are all members' or base tables and whose computed parameterized tables all have, at each assignment, the TableHash of a member's parameterized table at that assignment | int | a measurement; at least 0. These queries are not target queries |

The target queries of a state are decided by one rule, from the `TableHash`es of the parameterized tables of the state's members. A target query is a ground truth graph query g, written over the state's own members, that holds each of these:

- It is not a member of the state.
- It applies: each graph table that g reads is stood for by a member's parameterized table. A member's parameterized table stands for a graph table when the member's map {`Assignment` → `TableHash`} equals the graph table's map. Assignments are compared with each DET named by the digest of its values' `TableHash`es, so DETs of two programs with equal sets of value `TableHash`es match; two DETs of equal `QueryHash` have equal value sets, so they match too. A DET with one value is left out of the compare. This is a measurement, not an identity.
- It makes progress: some graph table that g computes has, at some assignment, a `TableHash` that no member's parameterized table has there. A graph query whose computed graph tables all have, at each assignment, a `TableHash` of a member's parameterized table there does not make progress. It is not a target query and is not a step of a state sequence. It is counted in `no_progress_queries`.

Where two members' parameterized tables stand for one graph table, g gives one target query for each choice of member. These are distinct `QueryHash`es whose parameterized tables have equal maps.

A target query is written over the members: its `body` is the body of a query of g with each read of a parameterized table that is not the chosen member's replaced by a read of the member's parameterized table, which stands for the same graph table. The sites of a replaced read are moved to the member's columns. A column of one table is paired with a column of the other that has its type and its cells at every `TableHash` the two tables share; the column labels do not decide the pairing. A target query that cannot be written this way is counted by reason and is not replaced by another.

## `StateSequence`

The order of states in one state sequence of type `union`. Each step adds one target query, which comes from a graph query, to the state.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `task` | its task | `TaskId` | |
| `seed` | the seed that chose its steps | int | at least 0; one sequence for each (task, seed) |
| `reached_goal` | whether its last state holds every goal parameterized table | bool | |
| `states` | its states, in step order | list of string (`Sample.id`) | not empty; the first is the root state; each state's set of `QueryHash` is the previous state's set plus one `QueryHash`, which is the `hash` of a target query of the previous sample; every state is of `task`. A sample can be in many sequences, and can be in one sequence once only |

The samples do not need it: a sample is one state and its target queries. Later stages use it:

- An evaluation that steps the writer along a sequence: at each state, the weight the writer gives to the target query that the sequence takes next. That target query is the one whose `hash` the next state adds.
- An evaluation that runs the writer from the root state, against the sequences that reach the goal.

A fit weighs each sample once, whatever the count of sequences that hold it or of visits that a search made to its state.

On disk, the source is `walk-seqs-SET.jsonl` in the `gold-union` folder, with each state given as its line number in `walk-states-SET.jsonl`. Those lines are keyed by (task, set of query identities), with the set of built graph tables kept as a measurement and `redundant_forms` as the count of queries that make no progress.

## `Split`

A task's assignment to a split. [Split design](split.md) gives which tasks go to which split.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `task` | the task | `TaskId` | one `Split` for each task: no task is in two splits |
| `split` | its split | `SplitName` | every sample of the task has this split |

Further invariants:

- No fit uses a sample of a `held-out` task.
- A statistic over tasks (a normalization, a vocabulary) is computed from `train` samples only.
- No record pools feature vectors of two tasks.

## Assignments

- A `TableVector` is per (parameterized table, assignment), keyed by (`QueryHash`, `Name`, `Assignment`). Constraint models are inside the tables, so they add no key; the vector handles them by "Several tables per ARC example" (see `TableVector`).
- A `QueryVector` is over the query's parameterized tables across its assignments, by these steps:
    1. The relation features (table row ratios, column origin, paint gain over the used parameterized tables) are computed per assignment of the query, against the used parameterized tables at the same assignment, restricted to the DETs each depends on. A used parameterized table's query has a use closure within the query's use closure, so its assignment follows from the query's. Where an ARC example has several tables, a feature is the mean over pairs of tables (see `QueryVector`).
    2. They combine over the query's assignments by the aggregates of the `AssignmentVector`: the assignment min, assignment mean and assignment max of each feature over those assignments.
- The count of assignments, `capped`, whether the tables differ, and the aggregates of the `TableVector`s of each parameterized table the query computes are that parameterized table's `AssignmentVector`. The QueryVector does not repeat them: a consumer takes them from the `AssignmentVector` of each of the query's Names.
- Features from the query's body do not depend on assignments.
- The aggregate set is part of the schema version.
- A `Sample` is per state, not per assignment, because the writer writes one query body that applies under every assignment.
- The loss on the computed parameterized tables is per target parameterized table: each parameterized table of `target_parameterized_tables` is one unit, whatever its count of assignments. Only the vectors are per (parameterized table, assignment).
- The split and the judge (whether a program solves its task) do not use assignments.

### The acceptance test of a written query

Below, a|t is an Assignment a restricted to the DETs that parameterized table t depends on, written as an `Assignment`. The empty tuple is the key of a parameterized table that depends on no DET.

- The test covers the Assignments at which both f's parameterized table and g's are computed. The engine caps each parameterized table's own walk (see `Assignment`). A target parameterized table whose own walk stopped at the cap is left out of credit and counted in `capped_target_parameterized_tables`.
- A target parameterized table t of g is matched by f when some output u of f has t's Type and, at every Assignment a that the test covers, the TableHash of u at a|u equals the TableHash of t at a|t. Names are not compared, so a RULE can match one INIT output of g.
- A parameterized table that matches at some assignments and not at others is not matched.
- Where f is itself a DET, its values are in no assignment of the state. Then f and g are compared by the sets of the TableHashes of their values, at each assignment of the state over the DETs they use.
- Each matched target parameterized table counts once. Credit and loss are per target parameterized table.
- f is accepted for g when all of g's parameterized tables match.

This is a judgement about computed parameterized tables. It makes no claim about how a parameterized table was derived.

## Measurements, not identities

`TableHash` is a measurement only. It is never the identity of a parameterized table or of a member of a state. These uses of it are measurements:

- Table recall against the ground truth: the union graph merges the parameterized tables of ground truth programs by their maps {`Assignment` → `TableHash`}.
- Features of a member's parameterized table, for example whether its hash equals another member's TableHash in the state.
- The prune flags of a search score: a parameterized table's hash equals another member's TableHash in the state, and its hash was seen before in that search. A score may use them. Nothing merges by them.
- The replacement of a graph table by a member's parameterized table in a target query.
- The value hash of a DET in an `Assignment`. It serves to write a key (`ParameterizedTable`, `Assignment`); the `ParameterizedTable` and its query's `QueryHash` are the identity.
- The acceptance test of a written query.

## Settled calls

- The user's premise: if two queries compute parameterized tables whose tables have equal `TableHash`, neither is derived from both queries; in a state, each parameterized table is computed by exactly one query.
- Depth counts from 0 over the state's own use edges: a member's parameterized table that uses no other member's parameterized table has depth 0.
- The cap on each parameterized table's walk stays (see `Assignment`). A target parameterized table whose walk stopped at the cap is left out and counted.
- In one ground truth program, no parameterized table is computed by several queries. A graph table can be computed by queries of several ground truth programs.
- OUT queries are not target queries.
- DEMONSTRATED is out of scope: the writer does not write it, and a task whose ground truth needs it is out of fits, scores and search counts, with that reason recorded.
- `*` is not in a query's identity or body. `^` is in them in a key group, where it selects the key columns. In an OUT, `^` is dropped.
- Held-out tasks are never in a fit.
- States come from the state sequences of type `union`, one sample for each distinct (task, set of `QueryHash`).
- The lib's relations and components are not in the state.
- Features computed from the query's body go in the query's `QueryVector`, not into a parameterized table's `TableVector`.
- The user's addition: each member of a state has one `QueryVector`, computed over all its Names and assignments, so a learned function over the whole state takes queries as its units.
- A state's use edges include the base tables that a member uses.
- The `TableVector`, the `TableHash` and the table row counts come from the full tables of every parameterized table at every assignment.

## Staleness

Each output (a set of records of one type for one set of tasks) carries a `Provenance`.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `versions` | each query the output depends on: the `TableHash`, `TableVector`, `QueryVector` and `QueryHash` versions, the canonical text's, the split's, and the engine build's | map of string to string | |
| `inputs` | each input the output was made from, with the hash of its content | map of string to string | an input that is itself an output enters with the hash of that output |
| `task_inputs` | for each task, the hashes of that task's inputs | map of `TaskId` to (map of string to string) | present where the output is made per task |

A consumer tells that its data is stale by these steps:

1. It compares each item of `versions` with the version its code expects.
2. It compares each hash of `inputs` with the hash of that input as it is now.
3. Any difference means the output is stale. `task_inputs` names the tasks that changed.
4. An output made from a stale output is stale too, since it holds that output's hash among its `inputs`.
