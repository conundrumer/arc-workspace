# Sample data: type contract

Status: record. The [feature specification](../feature-spec/feature-spec.md#what-in-the-sample-contract-changes) lists what it changes here. Nothing here is built. This contract gives the types of the sample data and the invariants that every implementation of the build must hold. It makes no claim about the language of a field. It says where the `TableVector` is computed (see `TableVector`).

## Terms

- A **task** is one ARC task. Its **examples** are its train pairs and its test inputs; each example has a kind (train or test) and an index. A **test output** is the output grid of a test pair. No field of this contract is computed from a test output.
- A **ColumnValue** is a value of a column's type, such as a Color or a Position. A **Row** is a map Column → ColumnValue. A **TableRows** is a set of Row. A **Type** is a set of Column, where a Column is a field with a column type, with no name and no order.
- A **parameterized table** is a base table or an output of a query. It has one Type, fixed by its query. The **base tables** of a task are `input`, `ex_input` and `ex_output`. The lib's relations and components are operators in a body: none is a parameterized table, and none is in a state.
- A **query** is (body, inputs, outputs):
    - A **Reference** is an atom that uses a parameterized table: in the body of a RULE, DET or OUT, in a clause at an input port of an INIT's component, or in a part of a RIGID_DET. `inputs` maps each Reference to the parameterized table it uses.
    - A **Name** is the one output of a RULE, DET or CHOOSE, an output port of an INIT's component, or a part or the pose of a RIGID_DET. An OUT has none. `outputs` maps each Name to a parameterized table.
    - A query **computes** its outputs from the parameterized tables it **uses**, which are the parameterized tables its References use. An input port and an output port are places in a body: an input port is where an INIT's input clause stands, and an output port is where an INIT's output stands.
- The **use closure** of a query is the query, the queries that compute the parameterized tables it uses, and so on down to the base tables.
- A DET has one or more values. Each value is a TableRows of the DET's Type. A query **depends on** each DET in its use closure, and each of its parameterized tables depends on the same DETs. A DET is in its own use closure, so a DET's parameterized table depends on that DET. A **dependent query** of a DET is a query that depends on it.
- An **Assignment** over a set of DETs maps each DET to one of its values.
- A **constraint model** is one choice at each factor that a parameterized table uses on one example, a factor being a ONE pick, the rows of a CHOOSE, an open parameter, a DEMONSTRATED key or an Unfold tie. It is local to the parameterized table and the example, with no identity across examples.
- A **parameterized table** maps each Assignment over the DETs it depends on to a **table**: a Type and a set of TableRows. Each TableRows is at one example under one constraint model, and its example is read off its Example column. Example is a column of each row. Two TableRows are one when they hold equal rows. With no factor in use, there is one TableRows per example. The engine enumerates a parameterized table's assignments depth-first, DETs in dependency order and values in content order (see `Assignment` for its walk and its cap). The table **at** an assignment is the value of the parameterized table at that assignment.
- The new export has no count cap, and no table is counts-only at any assignment. Every table at every assignment has its full rows, and the `TableVector`, the `TableHash` and the counts are computed from them.
- A table is **counts-only** at an assignment (old export layout only, behind its flag, during the switch) when there are no rows to compute from there: the engine gives row counts only (more than 10,000 rows in one TableRows), or no run of its program finished it. Under the new export no table is counts-only.
- A **relabelling** of a query renames its variables, its own label, the labels of the parameterized tables it uses and the field names of computed parameterized tables, with no other change.
- A **state** is a set of queries, closed under inputs (see `State`). A **member** of a state is a query in that set.
- The **model** maps a state to a distribution over query bodies whose inputs are parameterized tables of the state. It writes a query, never an assignment.
- A **fit** is any step that sets, from data, the parameters of the model or of another learned function, or a statistic that one of them uses.

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
- Where a stored record, a vector or the export needs a key for a table at an assignment, the key is (`ParameterizedTable`, `Assignment`).

## `Assignment`

The key of a table at an assignment: an Assignment over the DETs the parameterized table depends on, a sorted tuple of (DET `QueryHash`, value hash). The DET `QueryHash` is the DET's own `QueryHash`, the one a state holds as a member.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `pairs` | each DET the parameterized table depends on, with its value | list of (`QueryHash`, value hash) | one pair for each DET the parameterized table depends on; sorted by `QueryHash` value; empty exactly when the parameterized table depends on no DET |

- A value is written as its **value hash**: a hash of the DET's own full table at that value that keeps the DET's column order, so two values that differ by a swap of two columns of one type have two value hashes. It is not the `TableHash` of that table, which is free of column order. The engine's export gives it in its `assignments` part.
- Where DETs of two programs are compared, as in acceptance and in the union graph, the sets of the TableHashes of their values are compared, not the value hashes.
- An Assignment over a larger set of DETs gives a table the key of its restriction to the DETs its parameterized table depends on. So two Assignments that agree on those DETs give the table one key.
- A DET with several values has one key for each value, since it depends on itself.
- A DET's own parameterized table is fixed when the DET closes, with every top-level label of its body as a column.
- A base table depends on no DET. Its one key is the empty Assignment.
- The engine prunes a DET to the columns its readers use, and walks the pruned DET's values. It writes a dependent table evaluated at a pruned value at every full value of the DET that projects to that pruned value. So one set of TableRows can repeat over several Assignments.
- The cap of 256 applies to the engine's walk over the values it evaluates (the pruned values). The expansion to full values comes after the walk and has no cap, so a parameterized table can have more than 256 Assignments. `capped` means the walk stopped at 256 values.

## The table at one assignment

The value of a parameterized table at one `Assignment`.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `types` | the column types of the table's Type | list of column type | |
| `rows` | its TableRows | set of TableRows | each TableRows holds the Example column and is at one example under one constraint model; equal TableRows are one. With no factor in use, there is one TableRows per example |

- Constraint models are inside the value. They are never in a `ParameterizedTable`, an `Assignment` or a `QueryHash`.
- In the old export layout, where the table is counts-only at that assignment, the value has `types` and no `rows`: the engine gives no rows for it. Under the new export the value always has its full `rows`.
- For each (`ParameterizedTable`, `Assignment`), the engine's export for the model and the state search writes the `TableVector` (see `TableVector`), the `TableHash` and plain row counts: the rows of each TableRows and the count of TableRows of each example. All three come from the full rows, with no count cap. It writes no rows. An export for feature development also writes the `RowStore` record (the full set of TableRows). During development, the `QueryVector` is computed in the Python feature build, over the row store. Open: under the new export the sample build has no source for it yet. Its relation features need the rows of a query's tables and of its used parameterized tables, so a settled QueryVector feature would move into the same crate and be computed at export, as a `TableVector` feature is.
- The tables of a parameterized table are computed from a state, not stored. The stored fields that come from them are the `TableHash` and the `TableVector` of each (`ParameterizedTable`, `Assignment`).

## `TableHash`

The hash of a table's Type and its Set of TableRows at one assignment: its column types and its set of TableRows. The Example column is part of each row, so the hash covers it. Opaque: a consumer compares hashes and does not decode them. It is a measurement on a table. It is never the identity of a parameterized table or of a member of a state: two parameterized tables whose tables have equal `TableHash` are not one parameterized table.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `version` | the definition of the hash | string | two hashes compare only under one version |
| `kind` | what the hash is computed from | `content` under the new export, which has no other value; in the old export layout, behind its flag, one of `content`, `counts_only` | in the old layout, `counts_only` exactly when the table is counts-only at that assignment |
| `value` | the hash | string | see below |

Properties of a `content` hash, under one version:

- Two tables at two assignments have one hash exactly when they have equal content: equal column type multisets, and a one-to-one map of columns that keeps each type, under which the two sets of TableRows are equal, the Example column mapping to the Example column. A hash collision is the only exception.
- The hash does not depend on column labels, column order, row order, the order in which the engine gives constraint models, marks, the session, the process, the machine, or the order in which the union names parameterized tables.
- The hash does not depend on a test output.
- It compares across tasks.

Properties of a `counts_only` hash (old export layout only, behind its flag, during the switch):

- It is computed from the column types and the row counts at one assignment. The `Assignment` is not in the hash. It makes no claim about content: two counts-only tables with equal types and counts have one hash, and that collision is a known limit. With the new export every table gets a `content` hash from its full rows, so a counts-only hash remains only in the old layout.
- It compares only within one task.

## `RowStore`

The TableRows of each table at each assignment, for feature development only. The engine's export writes it once per run. The Python feature build reads it. The export for the model and the state search writes no rows.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `key` | the table at an assignment | (`ParameterizedTable`, `Assignment`) | one record for each of the parameterized table's assignments |
| `hash` | its TableHash | `TableHash` | |
| `value` | the table at that assignment (see "The table at one assignment") | `types` and `rows` | `rows` is the full set of TableRows, with no count cap; absent only in the old layout, exactly when `hash.kind` is `counts_only` |
| `counts` | plain row counts | the rows of each TableRows, and the count of TableRows of each example | |

- A change of the feature code does not write it again. A change of the engine or of the export does.

## `TableVector`

The per-table features of one table at one assignment, keyed by (`QueryHash`, `Name`, `Assignment`), or of one base table, keyed by its `BaseName`. Each feature is computed from the table at that assignment together with the base tables of its task. A parameterized table has one vector for each of its assignments.

The model takes features. Where a vector is computed:

- In the engine at export, for each (`ParameterizedTable`, `Assignment`), from the table's full rows. The samples and the state search take this vector.
- In the Python feature build, over the `RowStore`, during development. A feature change runs the feature build again and does not run the export.
- A feature is written once, in the crate `engine/arclog-features`, which has no engine dependency. The export calls the crate. A small Python module, `arclog_features`, calls the same functions over the row store. The crate's input for a table at an assignment is:
    - `types`: the type name of each column, as `ValueType`'s `Debug` spells it, without the Ident source. Position, Box and Offset are separate types.
    - The cells as i32, in the export's encoding.
    - The TableRows, grouped on the Example column.
    - The task's train pairs, for every table.
    - `capped`: true when the engine's walk of the parameterized table stopped at the cap (see `Assignment`).
    - `task_level`: true when the engine evaluated the table once for the task, not once per example. This holds exactly when the table's example keys have one item, of kind 0. It is not the same as a table with no Example column.
- Each change to the crate's input or to a feature gives a new features version.
- A feature that Features-worker develops in Python moves into the crate when it settles. Until then it is in the Python feature build only.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `schema_version` | the definition of every feature | string | two vectors compare only under one schema version |
| `names` | the feature names | list of string | unique; the same list, in the same order, for every vector of one schema version, so storage may keep it once per version |
| `values` | the feature values | list of float | same length as `names`; NaN where a feature has no value for this table |

Invariants an implementation must hold, in the engine and in the Python feature build alike:

- Where both give a feature, both call the same function of the crate, so the two values agree under one schema version.
- No feature uses a column label, a mark, or an order: of columns, of rows, of constraint models, of atoms, or of the queries of a program. Where a feature needs a column order, the order is a function of content.
- No feature uses a test output.
- Where colors tie for the most common, the lowest color is taken.
- No feature uses the computing query: its body, kind, atom counts or depth. These go in the query's `QueryVector`.
- No feature uses the same parameterized table at another assignment, or another parameterized table of the same query.
- The vector is a function of the table's content at that assignment and the task's base tables. So, under one schema version and one implementation, it is bit-equal across sessions, processes and machines, and two tables of one task with one `TableHash` have one vector. Where a feature uses a subset of the rows, the subset is chosen by content.
- In the old export layout, where the table is counts-only at that assignment, the vector is defined: the feature `counts_only` is 1, every feature that is computed from the column types alone has its value, and every other value is NaN. For every other table, `counts_only` is 0, and so it is for every table under the new export.

### Several TableRows per example

Agreed with Sampler-worker.

An example of a table at one assignment can have more than one TableRows. Search-worker's union check found such tables: 100 of 3,933 replayed training tables, 23 of 410 in the 37, and 0 on the ramp. The vector handles them by these rules:

- The computation groups the TableRows on the Example column. Per example, it computes the count of its distinct TableRows, the most rows over them, and the hash of its set of TableRows.
- Each per-example quantity that a feature is computed from (a row count, an overlap with the train output, a color set) is computed per TableRows and averaged over the example's TableRows. The feature then combines over examples as it defines.
- Two features are computed from the count of TableRows per example: its mean and its max over examples.
- So the vector has a fixed length. For a table with one TableRows in every example, each feature has the value it has on that one TableRows.
- The schema version fixes these rules, as it fixes the aggregates of the `AssignmentVector`.

## `AssignmentVector`

The features of one parameterized table across its assignments, keyed by (`QueryHash`, `Name`), or of one base table, keyed by its `BaseName`. A base table has one assignment. Each feature is computed from the parameterized table's `TableVector`s and `TableHash`es at its assignments.

| Feature | Meaning |
|---|---|
| `count` | the count of its assignments |
| `capped` | 1 when the engine's walk of the table stopped at the cap (see `Assignment`), else 0 |
| `distinct` | the count of distinct `TableHash`es over its assignments, divided by `count` |
| `differ` | 1 when its tables differ at two assignments, that is, when it has two or more distinct `TableHash`es, else 0 |
| `<f>:min`, `<f>:mean`, `<f>:max` | for each `TableVector` feature `<f>`, its min, mean and max over the assignments |

Invariants:

- The vector is a function of the parameterized table's tables at its assignments. No feature uses the order of the assignments.
- The sample build and the writer compute it with one function, so that training and serving give one value.
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

The engine's canonical form sorts the branches of an OR with `members` (`canonical/form.rs:891-911`), as it sorts the conjuncts of a body. This is decided. Until that change is in the engine, its canonical form keeps the branches in their written order (`canonical/walk.rs:156-160`), and the property "under order of the branches of an OR" does not hold.

## `BaseTable`

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `name` | which base table | `BaseName` | |
| `hash` | its TableHash, as a measurement | `TableHash` | kind `content` |
| `vector` | its features | `TableVector` | |

## `BuiltTable`

One table of a member of a state at one assignment, keyed by (`parameterized_table`, `assignment`).

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `parameterized_table` | the parameterized table | `ParameterizedTable` | `parameterized_table.query` is a member of the state |
| `assignment` | the key of the table at that assignment | `Assignment` | over the DETs `parameterized_table` depends on; one of its assignments |
| `hash` | its TableHash, as a measurement | `TableHash` | not an identity: two tables can have one `hash`, and both stay |
| `vector` | its features | `TableVector` | equal to the vector of every other table of the task with this hash |
| `inputs` | the parameterized tables that `parameterized_table.query` uses, each at its assignment | list of (`ParameterizedTable`, `Assignment`) | a base table at the empty `Assignment`, or the key of a `BuiltTable` of the state with a lower `depth`; each `Assignment` is `assignment` restricted to the DETs that parameterized table depends on; no duplicates |
| `depth` | its depth over the state's own use edges | int | 0 where `inputs` holds no member's parameterized table; else 1 + the greatest `depth` among the members' parameterized tables of `inputs`. Base tables do not count. Equal for every `BuiltTable` of one query |
| `graph_table` | the name of the graph table it stands for | optional string | a row id; no model input uses it. Present only where its `parameterized_table` stands for a graph table (see `Sample`) |

A member's `BuiltTable`s, their `hash` and `vector`, and its query's `QueryVector` are functions of the query and its use closure. They are stated once per query, and they are the same in every state that holds the member.

## `QueryVector`

The features of one query, one level above its parameterized tables. Each feature is computed from the query's used parameterized tables, the parameterized tables it computes, the relation between them, and the base tables of its task. One optional family is computed from the query's body. A QueryVector does not repeat a `TableVector`: a consumer takes those from the `BuiltTable`s and the `BaseTable`s.

A **used parameterized table** of a query is a `ParameterizedTable` of its `inputs`: a member's parameterized table or a base table. At one assignment of the query, a used member's table is at that assignment restricted to the DETs the used parameterized table depends on. Used parameterized tables are sorted with the base tables first, in the order of `BaseName`'s values, then the members' parameterized tables by (`QueryHash` value, `Name`).

A query has one QueryVector, computed over all its Names and all its assignments (see "Assignments"). The assignments of a query are the assignments of its parameterized tables. At one assignment, where a feature is computed per computed table, the value is the greatest over Names, unless the schema version defines another aggregate.

Where an example has several TableRows (see `TableVector`, "Several TableRows per example"), a feature over the query's table and a used table is computed per pair of TableRows on that example (the query's TableRows and the used table's TableRows) and averaged over those pairs. It is then aggregated over assignments (see "Assignments"). Agreed with Sampler-worker.

The mean over all pairs is a known approximation:

1. The query and a table it uses can share a factor, such as a pick that both use. Then their TableRows on one example come from joint constraint models: the query's TableRows under one choice goes with the used table's TableRows under the same choice.
2. A mean over all pairs then mixes choices.
3. It is still a defined measurement, and it equals the mean over the paired TableRows when no factor is shared.
4. The engine could give the pairing: `models_with_picks` gives each constraint model's choice at the named picks (`engine/arclog/src/eval/models.rs:307-314`). That needs an engine change.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `schema_version` | the definition of every feature, of `use_names`, of `column_origin`, and of the aggregates over assignments | string | two vectors compare only under one schema version |
| `names` | the names of the query's features | list of string | as `TableVector` |
| `values` | their values | list of float | as `TableVector` |
| `use_names` | the names of the query's features against one used parameterized table | list of string | unique; the same list, in the same order, for every vector of one schema version |
| `per_use` | for each used parameterized table, the query's features against it | list of (`ParameterizedTable`, list of float) | one item for each used parameterized table; no duplicates; in the sort order of used parameterized tables; each list has the length of `use_names`; NaN where a feature has no value |
| `column_origin` | for each `Name`, where each column of its parameterized table comes from | list of (`Name`, list of (column type, set of `ParameterizedTable`)) | one outer item for each `Name` of the query, sorted by `Name`; one inner item for each column of that parameterized table; the set is empty exactly when the column is new; inner items sorted by column type, then by the set. It is computed from the query's body and component, so it is one value for all assignments |

A column of a computed parameterized table is **carried over** from a used parameterized table when the query binds that column at a column of an atom that uses that parameterized table. It can be carried over from more than one used parameterized table. A column that is carried over from no used parameterized table is **new**. Where the query's body does not bind the columns of its parameterized table (an INIT output), the schema version defines their origin from the component.

Invariants an implementation must hold:

- No feature uses a column label, a mark, or an order: of columns, of rows, of atoms, of the branches of an OR, of the queries of a program, of assignments, or of the used parameterized tables as the query writes them. `column_origin` and `per_use` write a used parameterized table as its `ParameterizedTable`, never by a label or by its position in the query. Where a feature needs an order, the order is a function of hashes and content.
- No feature uses a test output.
- The vector is a function of the query's `QueryHash`, the content of its used and computed tables at each of its assignments, and the task's base tables. So, under one schema version and one implementation, it is bit-equal across sessions, processes and machines.
- In the old export layout, where a used or computed table is counts-only at an assignment, each feature that needs its rows is NaN at that assignment.
- The family computed from the query's body is optional: a schema version holds all of it or none of it. No feature of it uses a label name.

A QueryVector is stated once per query: one `QueryHash` has one QueryVector in every state that holds it.

### Families

The sources are the rows of the [per-table feature inventory](inventory.md). "Hand" is the scope pick's node score, "round 1" is node score refit round 1, "M2" is the derived-pick model, and "M-TS" is the node rank model with the `Form shape` group. Features against one used parameterized table are in `per_use`. All others are in `values`. The features of the first three families are computed per assignment and enter as their aggregates (see "Assignments").

Relation to used parameterized tables:

| Feature | Status |
|---|---|
| the member's `depth` | exists: hand `depth`, round 1 `dp_form_depth`, M2 `d1` .. `d4` (one-hot). Hand `depth` is lowered when an equal table merges in. Here it is the `depth` of `BuiltTable` |
| count of the members' parameterized tables it uses | exists: hand `n_parents` and `link_np`; M2 `root` (the count is 0) |
| row count against the greatest row count of the members' parameterized tables it uses | exists: hand `link_row_ratio` |
| its Position cells are a proper subset, a proper superset of, or disjoint from those of a member's parameterized table it uses | exists: hand `link_filter`, `link_grow`, `link_disjoint` |
| row count against that used parameterized table's row count, per example (`per_use`) | new |
| share of its column types that that used parameterized table also has (`per_use`) | new |

Column origin:

| Feature | Status |
|---|---|
| `column_origin` | new |
| count of columns carried over; count of new columns | new |
| count of used parameterized tables from which no column is carried over | new |

Computed from the table together with the base tables, against the used parameterized tables:

| Feature | Status |
|---|---|
| the greatest paint or fill gain among the members' parameterized tables it uses | exists: hand `link_parent_gain` |
| its gain less that greatest gain; whether it is greater | exists: hand `link_adds`, `link_better` |
| share and count of its fixed or covered cells that no member's parameterized table it uses fixes or covers | exists: hand `link_new_cells`, `link_new_count` |
| the greatest share of cells added by the union with one member's parameterized table it uses | exists: hand `link_pair_union` |
| its paint gain less that used parameterized table's paint gain (`per_use`) | new |
| share of its fixed cells that that used parameterized table does not fix (`per_use`) | new |

Computed from the query's body (optional):

| Feature | Status |
|---|---|
| kind | exists: round 1 `dp_kind` |
| component: the INIT pattern or DET op | exists: M-TS `sh_op_*` (42) |
| count of Names | exists: M2 `lnrel` |
| counts of atoms, NOT atoms, OR branches, ORs, comparisons, ALL, IF; NOT is present when the count of NOT atoms is above 0 | exists: M-TS `sh_atoms`, `sh_neg_atoms`, `sh_or_branches`, `sh_n_or`, `sh_cmp`, `sh_all`, `sh_if` |
| uses of base tables and of parameterized tables of queries | exists: round 1 `dp_form_reads`; hand `clause_atoms`; M-TS `sh_n_input`, `sh_n_ex_input`, `sh_n_ex_output`, `sh_form_reads`, `sh_form_reads_distinct`, `ce_reads`, `ce_distinct`, `ce_fixed`, `ce_negated`, `ce_union`, `ce_src_*` (4) |
| count of labels; count of labels with 2 or more sites | exists: M-TS `sh_labels`, `sh_labels_multi` |
| count of atoms of each lib relation | exists: M-TS `sh_rel_*` (79) |

Not in a QueryVector:

- M-TS `sh_rport_*` (21): they are computed from label names. M-TS `sh_head_cols`: it is computed from the table, and `TableVector` has the column count. Hand `clause_len`: it is computed from the order of the written body.
- M2's 36 features marked "vs tables", except the 5 above (`d1` .. `d4`, `root`):
    - 4 depend on members other than the query's used parameterized tables, so they are functions of `State`: `dmax`, `deep`, `leaf`, `lread`.
    - 27 are about the pick or the body being drawn: `tin`, `tinf`, `nosc`, `dupt`, `dupk`, `dr_self`, `dr_sib`, `dr_anc`, `dr_desc`, `dr_par`, `dr_key`, `dr_type`, `x_nod_*` (3), `x_<place>_leaf` and `x_<place>_dmax` (10), `x_r2_self`, `x_r2_leaf`.

Counts of source features, by family:

| Family | Existing | New |
|---|---|---|
| Relation to used parameterized tables | 13: hand 7, round 1 1, M2 5 | 2 |
| Column origin | 0 | 4 |
| Against the used parameterized tables, with the base tables | 6: hand | 2 |
| Query body | 148: M-TS 144, round 1 2, hand 1, M2 1 | 0 |

## `State`

A set of queries, closed under inputs, with the base tables. Closed under inputs means: each Reference of a member uses a base table or a parameterized table that another member computes. That set is the whole identity. Each member's parameterized tables are computed from it, with a table at each assignment, and are not stored. The fields below that come from them are the hashes and vectors of those tables.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `id` | the state's identity | string | a hash of the sorted set of the members' `QueryHash`es |
| `members` | the members' parameterized tables, each at each of its assignments | set of `BuiltTable`, keyed by (`parameterized_table`, `assignment`) | closed under inputs; for each member, one `BuiltTable` for each `Name` and each of that parameterized table's assignments. Stored sorted by (`depth`, `parameterized_table`, `assignment`); the order serves only storage |
| `query_vectors` | each member's `QueryVector` | map of `QueryHash` to `QueryVector` | one pair for each distinct `parameterized_table.query` of `members`. Kept per query, not per `BuiltTable`, since a member has one `BuiltTable` for each `Name` and assignment and one QueryVector for all of them |
| `given` | the base tables | list of `BaseTable` | one `BaseTable` for each `BaseName`. Base tables are in every state and are not members |

Two states are equal exactly when their sets of `QueryHash` are equal. The root state has no members.

Per-table fields over use edges (counts of parameterized tables that use a parameterized table, ancestors, the features of the parameterized tables that use a parameterized table, and whether a table's `hash` equals another member's TableHash) are functions of `State`. They are not stored. The features of a member over its own used parameterized tables are in its `QueryVector`.

## `TargetQuery`

One target query at a state: a query (body, inputs, outputs) that the model is trained to write.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `hash` | the query's identity | `QueryHash` | not a member of the state |
| `kind` | the query's kind | `QueryKind` | |
| `hash_exact` | whether `hash` holds the properties of `QueryHash` for this query | bool | false only where an implementation cannot prove them, for example where a search for the canonical labelling stopped at its bound |
| `body` | the query's body as canonical text, for writing | optional string | present: a function of `hash`, so equal hashes have equal bodies. It writes each Reference as the `ParameterizedTable` it uses |
| `body_decodes` | whether the engine's decoder takes `body` in its written order | optional bool | present exactly when `body` is present |
| `inputs` | the parameterized tables of its References | set of `ParameterizedTable` | each is a base table or the `parameterized_table` of a `BuiltTable` of `State.members` |
| `outputs` | its Names | list of `Name` | sorted; each output's parameterized table is (`hash`, that `Name`) |
| `computes` | each of its tables at each assignment | list of (`Name`, `Assignment`) | one pair for each `Name` and each assignment of its parameterized table over the state; a parameterized table whose walk stopped at the cap is left out (see `Sample`); sorted by (`Name`, `Assignment`) |
| `computes_hashes` | the TableHash of each pair of `computes`, as a measurement | list of `TableHash` | same length and order as `computes` |
| `computes_vectors` | the features of each pair of `computes` | list of `TableVector` | same length and order as `computes`. Equal to the vector of every other table of the task with that hash. A training target value, not a model input at this state |
| `query_vector` | the query's features | `QueryVector` | computed from `inputs` and the tables of `computes`. A training target value, not a model input at this state, as `computes_vectors` |

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
| `frontier_depth` | the least depth, in the gold graph, among the graph queries that give the target queries | int | at least 0. It is computed from gold, so it serves only to group counts. No model input uses it |
| `no_progress_queries` | the count of gold graph queries, not members of the state, whose used parameterized tables are all members' or base tables and whose computed parameterized tables all have, at each assignment, the TableHash of a member's table | int | a measurement; at least 0. These queries are not target queries |

A target query at a state is a query that holds each of these:

- It is not a member of the state.
- Each parameterized table it uses is a member's parameterized table or a base table.
- It makes progress: some parameterized table it computes has, at some assignment, a TableHash that no member's table has. A query whose computed tables all have hashes of members' tables is not a target query and is not a step of a state sequence. It is counted in `no_progress_queries`.
- It comes from a gold graph query, written over the state's own members: each graph table that the graph query uses is replaced by a member's parameterized table that stands for it. A member's parameterized table stands for a graph table when the member's map {`Assignment` → `TableHash`} equals the graph table's map. Assignments are compared by their DET value hashes, so that equal DETs of two programs match. Where the two programs' DETs have equal `QueryHash`es, the (DET `QueryHash`, value hash) pairs are compared. Otherwise the compare first pairs each DET of one program with one DET of the other by equal sets of the TableHashes of their values; sorting the value hashes within a tuple would lose which DET holds which value (Sampler-worker's note). This is a measurement, not an identity.

Where two members' parameterized tables stand for one graph table, the graph query gives one target query for each choice of member. These are distinct `QueryHash`es whose parameterized tables have equal maps.

The rule above is decided: a graph table is a map {`Assignment` → `TableHash`}; DETs with different `QueryHash`es pair by equal sets of the TableHashes of their values; reach is per assignment. The union graph merges parameterized tables by the hash that `table_key` computes over all assignments today, so it must be rebuilt with a table per (parameterized table, assignment) and its map. That rebuild waits on the engine's export change.

## `StateSequence`

The order of states in one state sequence of type `union`. Each step adds one target query, which comes from a graph query, to the state.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `task` | its task | `TaskId` | |
| `seed` | the seed that chose its steps | int | at least 0; one sequence for each (task, seed) |
| `reached_goal` | whether its last state holds every goal parameterized table | bool | |
| `states` | its states, in step order | list of string (`Sample.id`) | not empty; the first is the root state; each state's set of `QueryHash` is the previous state's set plus one `QueryHash`, which is the `hash` of a target query of the previous sample; every state is of `task`. A sample can be in many sequences, and can be in one sequence once only |

The samples do not need it: a sample is one state and its target queries. Later stages use it:

- An evaluation that steps the model along a sequence: at each state, the weight the model gives to the target query that the sequence takes next. That target query is the one whose `hash` the next state adds.
- An evaluation that runs the model from the root state, against the sequences that reach the goal.
- A weight for each sample in a fit: the count of sequences that hold it.

On disk, the source is `walk-seqs-SET.jsonl` in the gold union folder, with each state given as its line number in `walk-states-SET.jsonl`. Those rows are keyed by (task, set of query identities), with the set of built graph tables kept as a measurement and `redundant_forms` as the count of queries that make no progress.

## `Split`

A task's assignment to a split. Which tasks go to which split is a separate design.

| Field | Meaning | Type | Invariants |
|---|---|---|---|
| `task` | the task | `TaskId` | one `Split` for each task: no task is in two splits |
| `split` | its split | `SplitName` | every sample of the task has this split |

Further invariants:

- No fit uses a sample of a `held-out` task.
- A statistic over tasks (a normalization, a vocabulary) is computed from `train` samples only.
- No record pools rows of two tasks.

## Assignments

- A `TableVector` is per (parameterized table, assignment), keyed by (`QueryHash`, `Name`, `Assignment`). Constraint models are inside the table, so they add no key; the vector handles them by "Several TableRows per example" (see `TableVector`).
- A `QueryVector` is over the query's parameterized tables across its assignments, by these steps:
    1. The relation features (row ratios, column origin, paint gain over the used tables) are computed per assignment of the query, against the tables of the used parameterized tables at the same assignment, restricted to the DETs each depends on. A used parameterized table's query has a use closure within the query's use closure, so its assignment follows from the query's. Where an example has several TableRows, a feature is the mean over pairs of TableRows (see `QueryVector`).
    2. They combine over the query's assignments by the aggregates of the `AssignmentVector`: the min, mean and max of each feature over those assignments.
- The count of assignments, `capped`, whether the tables differ, and the aggregates of the `TableVector`s of each parameterized table the query computes are that parameterized table's `AssignmentVector`. The QueryVector does not repeat them: a consumer takes them from the `AssignmentVector` of each of the query's Names.
- Features from the query's body do not depend on assignments.
- The aggregate set is part of the schema version.
- A `Sample` is per state, not per assignment, because the model writes one query body that applies under every assignment.
- The loss on the computed parameterized tables is per target parameterized table: each parameterized table of `target_parameterized_tables` is one unit, whatever its count of assignments. Only the vectors are per (parameterized table, assignment).
- The split and the judge (whether a program solves its task) do not use assignments.

### The acceptance test of a written query

Agreed with search-worker and Sampler-worker.

Below, a|t is an Assignment a restricted to the DETs that parameterized table t depends on, written as an `Assignment`. The empty tuple is the key of a parameterized table that depends on no DET.

- The test covers the Assignments at which both f's table and g's table are computed. The engine caps each parameterized table's own walk (see `Assignment`; `determination.rs:426-433`). A target parameterized table whose own walk stopped at the cap is left out of credit and counted in `capped_target_parameterized_tables`; the walk's stop flag (see `QueryVector`) tells that it stopped.
- A target parameterized table t of g is matched by f when some output u of f has t's Type and, at every Assignment a that the test covers, the TableHash of u at a|u equals the TableHash of t at a|t. Names are not compared, so a RULE can match one INIT output of g.
- A parameterized table that matches at some assignments and not at others is not matched.
- Where f is itself a DET, its values are in no assignment of the state. Then f and g are compared by the sets of the TableHashes of their values, at each assignment of the state over the DETs they use.
- Each matched target parameterized table counts once. Credit and loss are per target parameterized table.
- f is accepted for g when all of g's parameterized tables match.

This is a judgement about computed parameterized tables. It makes no claim about how a parameterized table was derived.

## Measurements, not identities

`TableHash` is a measurement only. It is never the identity of a parameterized table or of a member of a state. These uses of it are measurements:

- Reach against gold: the union graph merges the parameterized tables of gold programs by their maps {`Assignment` → `TableHash`}.
- Features of a member's table, for example whether its hash equals another member's TableHash in the state.
- The prune flags of a search score: a table's hash equals another member's TableHash in the state, and a table's hash was seen before in that search. A score may use them. Nothing merges by them.
- The replacement of a graph table by a member's parameterized table in a target query.
- The value hash of a DET in an `Assignment`. It serves to write a key (`ParameterizedTable`, `Assignment`); the `ParameterizedTable` and its query's `QueryHash` are the identity.
- The acceptance test of a written query.

## Settled calls

- The user's premise: if two queries compute parameterized tables whose tables have equal `TableHash`, neither is derived from both queries; in a state, each parameterized table is computed by exactly one query.
- Depth counts from 0 over the state's own use edges: a member's parameterized table that uses no other member's parameterized table has depth 0.
- A parameterized table is written as (`QueryHash`, `Name`), and a base table by its `BaseName`. A table is the value of a parameterized table at an `Assignment` over the DETs it depends on. There are no assignment columns. So a member's parameterized tables, hashes, vectors and QueryVector are stated once per query.
- A parameterized table maps each `Assignment` to a table: a Type and a set of TableRows, one per constraint model on each example, with equal TableRows being one. Each TableRows holds the Example column. Constraint models are inside the table, never in a `ParameterizedTable`, an `Assignment` or a `QueryHash`. The TableHash covers the column types and that set of TableRows.
- The engine caps its walk of each parameterized table (see `Assignment`). A target parameterized table whose walk stopped at the cap is left out and counted.
- In one gold program, no parameterized table is computed by several queries. A graph table can be computed by queries of several gold programs.
- A written query is accepted by the acceptance test of a written query (see "Assignments").
- OUT queries are not target queries.
- `*` is not in a query's identity or body. `^` is in them in a key group, where it selects the key columns. In an OUT, `^` is dropped.
- Held-out tasks are never in a fit.
- The target queries of a state are the gold graph queries written over its members that make progress: some parameterized table they compute has, at some assignment, a TableHash that no member's table has. A query that makes no progress is not a target query and not a step of a state sequence, and its count per state is a measurement.
- States come from the state sequences of type `union`, one sample for each distinct (task, set of `QueryHash`).
- The lib's relations and components are not in the state.
- Features computed from the query's body go in the query's `QueryVector`, not into a table's vector.
- The user's addition: each member of a state has one `QueryVector`, computed over all its Names and assignments, so a learned function over the whole state takes queries as its units.
- A state's use edges include the base tables that a member uses.
- In the old export layout, a member whose table is counts-only at an assignment stays in the state, with a `counts_only` hash and the defined counts-only vector at that assignment. Under the new export no table is counts-only.
- The user's ruling: the new export has no count cap and no table is counts-only at any assignment. The `TableVector`, the `TableHash` and the counts come from the full rows of every table at every assignment. The counts-only kind stays only in the old layout, behind its flag. The cap on each parameterized table's walk (see `Assignment`) is not part of this ruling and stays.

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
