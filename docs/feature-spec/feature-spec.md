# Feature specification

The rules for the encoder from tables to features. [Arclog column types](arclog-types.md) gives what the engine knows about a column, which the features read.

## The objects

| Object | What it is |
|---|---|
| **Feature query language** | The set of all feature expressions: relational algebra with aggregates, lib joins and components. The grammar under "The generating set" defines it. |
| **Feature expression** | One feature as a tree of operators, with holes for a table and its columns. |
| **Ground expression** | A feature expression with its holes bound. Its value is what the encoder computes. |
| **Shape** | A ground expression with its table and that table's columns written as typed holes. It names one entry of a vector for every table. |
| **Generating set** | The primitives that feature expressions are made of. |
| **Feature library** | The written arclog source of the named compositions: `engine/lib/features.arclog`. |
| **Encoder** | The function that the library defines at a size: from a state's tables to the values of the features that the library names and of every ground expression up to that size. |

## Purpose

Features support the program search and do not replace it. A feature expression has the form of a query, so a ground expression of size d shows a learned model what a query of that size would compute. An encoder run at a size large enough to reach the output would be the search itself, done by brute force.

The features are a superset of the first version: a feature vector must give whatever the first version tells a learned model, in the forms of this specification. [Coverage of the first version](evaluation-protocol.md#coverage-of-the-first-version) measures this.

## Definition

- A **feature** is arclog: forms that read tables of a state and base tables, and an `EXPORT` form that says what they give.
- A solver extracts what it needs from a task in arclog, so arclog can state what a feature extracts. A feature is a solver's fragment with `EXPORT` in place of `OUT`.
- Feature forms run after the state's queries and are not added to the state. A learned model never reads them as part of a program.
- A feature's value is taken at one assignment, and a per-input value at one constraint model. Arclog's own rules say how often a form runs: a `RULE` per input, a `DET` once for a task, and an instance of a component by what its bodies read.
- A feature expression's table hole is bound to a parameterized table at one assignment, and the expression is evaluated on each of that parameterized table's tables. [Levels](../sample-build/contract.md#levels) gives how the values combine.

## What the language gives by construction

Each of these follows from the arclog rules, so no feature code and no check repeats it.

| Property | Source |
|---|---|
| Independent of the order of rows, columns and atoms | A relation is a set of rows. A column has no order. |
| No test output is read | `output` and `ex_output` contain train outputs alone. `ex_input` contains the test inputs too. |
| A color and a number never join | The checker. |
| Order tests apply to numbers alone | The checker. |
| No literal of a task type, and no number but `0` | The grammar. |
| An Ident joins only within its source | The checker. |

## The generating set

A feature expression is a term of this grammar. Each name is a primitive of the expander, and the checker decides which bindings are accepted.

```
Feature      ::= (nonempty Rel) | (cardinality Rel) | (value-set Rel Column+) | (ratio Rel Rel)

Rel          ::= Leaf
               | (project Rel Column+)
               | (select Rel Column Op Operand)
               | (join Rel Rel (Column Column)*)
               | (semijoin Rel Rel (Column Column)*)
               | (antijoin Rel Rel (Column Column)*)
               | (all Rel Rel (Column*) (Column Column)*)
               | (union Rel Rel (Column Operand)+)
               | (lib-join Rel LibRelation (LibColumn Operand)*)
               | (component Component InputBinding+ Port)

InputBinding ::= (Input Rel (KeyColumn*) (Field*))
Field        ::= Column | (Column+) | 0

Leaf         ::= a table hole | input | output | ex_input | ex_output | a program relation
               | a lib relation that needs no bound column | a proposer
Op           ::= = | != | < | <= | > | >=
Operand      ::= Column | 0
```

- `Column`, `KeyColumn`: a column of the relation in that node, by the names of "Column names" below.
- `LibRelation`, `LibColumn`: a `relation` or `macro` form of the registry, other than `pose_difference`, which takes Pose values, and one of its columns.
- `Component`, `Input`, `Port`: a component of the registry, one of its inputs, and one of its outputs.
- A proposer: a `proposer` form of the registry with no `domain` mark, read as the whole set of rows it gives. So it stands for no choice of a parameter. A domain belongs to determinations. The values of an orientation type come from a lib relation such as `dir_elem`, and the colors of a grid from a `project` of it.
- `output`: the train output of the current ARC example, with the columns `P` and `Col`. It has no rows on a test input. So a per-input feature can compare a table with the output of its own ARC example, at each constraint model. It stands where `input` stands in the rule that gives an instance's level, in the check of what a form reads, and in the frames, where its `P` stands in the current ARC example's output.

### Aggregates

The root is one aggregate over a relation.

| Aggregate | Value | On no rows |
|---|---|---|
| `nonempty` | whether the relation has a row | false |
| `cardinality` | its count of rows, over all its columns | 0 |
| `value-set` | the set of the values of its columns | the empty set |
| `ratio` | the first relation's count of rows over the second's, as an exact fraction | no value where the second has no rows, and otherwise 0 where the first has none |

Everything else is an operator under one of these. The number of distinct values of `x` is `(cardinality (project R x))`. The share of `R`'s rows that `S` matches is `(ratio (semijoin R S ...) R)`. Whether `x` determines `y` is whether `(ratio (component Singleton (member R (x) (y)) value) (project R x))` is 1. Whether one count is above, at or below another is whether their ratio is above, at or below 1. The greatest group size is a `value-set` over `Order`'s `maximal`.

`ratio` is a root because a vector combines each entry over the ARC examples on its own, which loses which value of one entry goes with which value of another at an ARC example. ARC examples differ in scale, and a count changes with scale. A ratio of two counts is what stays fixed, so an invariant across ARC examples of different sizes can show only there.

### Operators

- **`project`, `select`, `join`, `semijoin`, `antijoin`, `union`:** the operators of relational algebra. A `join` with no column pair is the Cartesian product, so a `select` over it is a theta join. A `semijoin` keeps the left relation's rows that have a match in the right, and an `antijoin` keeps those that have none.
- **`all`:** arclog's `ALL` form, which relational algebra calls division. `(all D B (x ...) (a b) ...)` gives the values of the outer columns `x ...` at which `D` has a row and each of `D`'s rows there has a match in `B`, by the column pairs. With no outer column it is a relation of no columns, which `nonempty` reads as true or false. On a domain with no rows it is false, so an empty relation makes no claim. `nonempty` states "some" and `all` states "every", so each claim has a form whose value is not the default. A universal written as an empty `antijoin` has the default value, and a vector leaves it out.
- **`lib-join`:** a join with a lib relation. Each column of the lib relation is bound to a column of the relation or to `0`, or is fresh. The checker's safety condition decides which bindings are accepted.
- **`component`:** one output port of a component. Each input binding writes one input from a relation: its key columns, then its fields.
    - Where the input has one column other than `key`, the fields are that column's, and several make a record. Where it has several, each field fills one column in the registry's order, and a list fills a type parameter's column with a record, as in `(pattern R () (Id (P Col)))`.
    - An input with a `key` column in the registry takes key columns of one count and type across its bindings, or none, where its rows apply to every key. A shared input takes none, and neither does an input whose first column has another name, as in `Inclusion` and `Quotient`.
    - An input with no binding takes its default, its value from the key, or no rows, as the registry gives.
    - The bindings can write any set of a component's inputs that the checker accepts.
    - `Unfold` has no binding, since its inputs read its own outputs, so a binding for it is a program. `DemonstrationConsistency` is out of scope.
`lib-join`, `component` and a proposer leaf read the registry for their names and columns, so the registry is the list.

### Size and the encoder

A feature expression's **size** is its count of distinct operators, without leaves and the root aggregate: a subexpression that appears twice counts once, since it is computed once. So `(ratio (semijoin R S) R)` has the size of `R`, plus that of `S`, plus 1. A `component` with k bound inputs counts as k, at least 1, since each bound input past the first combines one more relation, as a `join` does. A **part** is a composition that the library names, with holes, and its call counts as 1, whatever its expansion's size. So enumeration over parts reaches features that are large in operators, and the library's parts set which ones a small size reaches. The parts come from the fragments that recur across the train solvers, and from what the library's named features repeat. A feature that needs a part the library lacks shows which part to add.

Enumeration leaves out a `join`, `semijoin`, `antijoin`, `all` or `lib-join` with no column pair between its sides, since its count follows from its parts' counts. A product stands only under a `select` or a `lib-join` that relates its two sides. It leaves out a term that reads no column of its table, since its value follows from the row count, which the table's own `cardinality` gives. `nonempty` stands only over a relation with no columns. A `project` of all of a table's columns equals the table, and enumeration holds it as a term of its own: a shape is named by its text, so a statement has one name on tables of every width.

A term is **entailed** where its value follows from smaller terms on every table its type admits. Enumeration is typed, so an entailed term has no derivation and is never constructed. The typing rules are the preconditions and postconditions of [Structure of the search](structure.md#conditions), held in a relation's type.

- **Refinements:** a relation's type holds, beside its column types and frames, what is known of its values: the keys of its columns, each number's range, the relations a column is a subset of, the columns that are complete over an orientation type, and its row count where that is known.
- **Sources:** a base relation and a lib relation declare their refinements, and so does each component output, in the registry. A part's refinements follow from its fragment's body. A table's measured rows give no refinement, since a fact of its rows is contingent.
- **Rules:** each operator gives its output's refinements, its postcondition, from its inputs' refinements, its precondition, as an abstract transformer.
- **Ill-typed terms:** an operator application has no derivation where its refinements prove that it changes nothing, that its output is empty, or that its value is constant or follows from its input's row count. For example:
    - `(select T x >= 0)` over a `Nat` changes nothing.
    - A `semijoin` with a relation that `x` is a subset of changes nothing, and an `antijoin` with it is empty.
    - A `project` that keeps a key leaves the row count as it was.
    - A group count over a key of `T` is 1 at each group.
- **Normal forms:** where two orders of operators are equal by their rules, as a `select` and a `semijoin` over columns it does not change are, one order is generated.
- **Soundness:** no rule is taken from a corpus.

A rule need not be complete, since equivalence over negation and aggregates is undecidable, so a term that no rule rejects stays.

Two terms with equal values are not entailed by that alone. Where the table's rows could have given a different value, the equality is contingent, and both terms stay.

**The encoder at size d** gives, for each table, the value of every feature that the library names, at any size, and of every ground expression of at most size d that reads that table, at every binding the checker accepts. An expression that reads no table has one value on every table, and a base table is a table here, so it has an encoding of its own. So a version of the library and the registry, and a size, fix an exact and finite set of features. Enumeration takes the two relations of a binary operator or of a `ratio` in both orders, so the set of names does not depend on text order.

## How an expression expands

The expander turns each primitive into forms, by the rules below, and what reaches the checker is plain arclog. A macro of the library is a function from S-expressions to forms that names a composition of primitives, as `join-label` and `group-sizes` do.

```lisp
(fragment (join-label (?R relation) (?p column ?R) (?grid grid))
  "A relation's rows with a grid's color at a column of cells."
  (QUERY &q
    (?R (?p *) (*others ?R ?p))
    (?grid (:P ?p) (:Col (*new Col ?R))))
  (gives &q))

(fragment (group-sizes (?R relation) (?x column ?R))
  "The rows per value of a column."
  (INIT &c Cardinality
    (key ((?R (?x ^)))
      (member ((:m (others ?R ?x)))
        (?R ?x (*others ?R ?x)))))
  (QUERY &sizes (&c.size (:key (?x *)) (:N (*new N ?R))))
  (gives &sizes))
```

- **Forms:** `(fragment ...)` gives a relation with one label per column, which its `gives` names. An instance's output has a record column, so a fragment over a component ends in a `QUERY` that labels each column. `(feature ...)` ends in `EXPORT`.
- **`QUERY`** expands to a `RULE` or a `DET`, as "Per input or task-wide" below gives.
- **Holes** declare their kind in the signature: a relation, a column of a named relation, a grid, or a list of columns. A relation hole takes a table or another macro's call, so macros compose. A hole ranges over everything of its kind, and an expansion that the checker refuses is no feature, so no macro states which column types it applies to.
- **Labels:** a site on a column hole writes a label named by the column, with its first letter in upper case, since a field's name is PascalCase. `(?x *)` makes it, `(?x ^)` makes it a label of the key, and a bare `?x` joins it. A site whose label has its column's name is written as the bare label. A label that the macro writes for a column of its own takes `*new`, so it never clashes with a column bound to a hole.
- **Splices:** `(*others ?R ?x ...)` in a read writes a site with a fresh label for each column of the relation but those named, each label named by its column. `(others ?R ?x ...)` in a head writes those labels bare. Where no column remains, the head site that holds the splice is left out, since a site needs a label or a field site. `(*new N ?R)` makes the label `N`, with a suffix where `?R` already has that name.
- **Fresh names:** the relation names, the instance names and any label that a hole, a splice or `*new` does not write are fresh at each call.
- **Identity:** a ground expression's identity is the engine's canonical hash of its expansion, down to the base tables. Two expressions with one expansion give one value, under the name of the smaller one, and at equal size the first in text order.

### Column names

A derived relation's columns are its labels as written, so each operator's output has fixed names, and a caller reads them by those names.

- **A table:** a site needs a label, so an expansion addresses a table's columns by the labels of its program. No value depends on those labels, since only their equality matters. A vector entry's name contains none of them, since its shape writes them as holes. An instance's output has the fields of its key and of its records as columns, and a read writes them in the `:key` site and in the site of the record's column.
- **A grid:** `input` and `output` have `P` and `Col`, and `ex_input` and `ex_output` have `E`, `P` and `Col`.
- **A proposer:** the columns that the registry names.
- **`project`, `semijoin`, `antijoin`:** the left relation's names.
- **`all`:** the names of its outer columns, and no column where it has none. The domain's other labels are local to the `ALL` form.
- **`select`:** the left relation's names. With `=`, the second column is left out, since it equals the first, and the expansion writes one label at both columns. With `=` and `0`, the column is left out, since its value is known, and the expansion writes `0` at the column's site. The checker refuses `(= X Y)` and `(= X 0)` where a site of the same list made `X`. Each other `Op` writes a constraint beside the read.
- **`join`:** the left relation's names, then the right relation's other columns. A matched right column is left out, since it equals the left one.
- **`union`:** the left relation's names. Each pair aligns a left column with a right column or `0`, and the pairs name every column of both.
- **`lib-join`:** the left relation's names, then the lib relation's fresh columns. A `0` writes `0` at the column's site.
- **`component`:** the first binding's key column names, then the port's other columns. A column that the registry names in upper case keeps that name. A column that the registry names in lower case has a type parameter as its type, and it takes the names of the columns that the first binding of that parameter writes to it.
    - A later binding takes the first binding's key names. Where a type parameter has several columns, a later binding also takes the first binding's names as the record's field names, as in `(:m (:P Origin) Col)`, and other names give a fault when it runs.
    - The key clause reads the key columns of each binding that has them, in an `OR` where there are several, so a key that a later binding alone has stays. `domain` gives such a key, which counts 0.
    - A shared input, and a binding with no key columns, stands after the key clause.
- A name already taken takes the suffix `_2`, then `_3`.

### Per input or task-wide

An expression is **task-wide** where a leaf has an Example column (`ex_input`, `ex_output`, or a table with one), or is a proposer, since a proposer reads every ARC example. Its `QUERY` forms expand to `DET`. Every other expression is **per input**, and its `QUERY` forms expand to `RULE`.

In a task-wide expression:

- A per-input table is read in its lifted form, with a column `E`. `input` is read as `ex_input`, and `output` as `ex_output`.
- A lifted read gives the label `E` to the Example column, so it cannot read a table's own column named `E`. The expansion first copies that table by a `RULE`, with that column under `E_2`. It does so for every read of the table, so no form names a table's own column `E`, and an expression addresses that column as `E_2`.
- `E` is a column like any other. A binary operator pairs it only where its pairs list it, so a `join` without that pair compares one ARC example with another, and has `E` and `E_2`.
- A macro states no pairs. So its atom on a grid hole has a site on `E` that joins the `E` of the macro's relation, and it reads that ARC example's grid.
- A `component` pools over the ARC examples unless `E` is among its key columns, and a `project` that leaves out `E` pools too. An input's body keeps a site on `E` where its binding leaves `E` out, since a body that reads a per-input table with no such site makes the instance per input.
- A lifted read of `ex_input` contains the test inputs, and `ex_output` contains train outputs alone. So an `antijoin` with `ex_output` keeps every row of a test input.
- On a parameterized table with several constraint models at an ARC example, the expression has no value, since no one table stands for every ARC example. A `DET` that reads such a parameterized table gives a fault when it runs.

A proposer leaf expands to one form, by the proposer's entry in the registry. A body atom cannot read a proposer, so a later form reads that form's relation.

| Proposer | Form | What the relation contains |
|---|---|---|
| One column | `(DET &p X (SET))` | One value: every row over the whole task, or no rows. |
| Several columns | `(DET &p X)` | One value: every row over the whole task, or no rows. The checker refuses `(SET)` here. |

A native proposer takes these forms as a proposer written in arclog does. The other forms give something else:

- `(DET &p X)` over one column gives one assignment per row, which is a choice of a parameter. With no row, it gives no assignment, so a read of it has no rows.
- `(RULE &p X)` runs the proposer on that input alone, with `ex_output` empty. So `SharedColor` gives that input's colors, and `ChangedColor` gives no rows.

## `EXPORT` and values

`EXPORT` has the form of `OUT`: one atom or several, each selecting columns with `^`. An aggregate expands to it.

- No selected column: whether the relation has a row.
- Several atoms: the product of their projections, as a two-atom `OUT` gives. A `ratio` exports its two counts, each from its own atom, so arclog divides nothing. The encoder reduces the two to lowest terms outside arclog, which gives the exact fraction.
- No feature compares a number with a literal. It exports the number.

So `0` and "no value" differ. `cardinality` gives `0` on no rows. A ground expression has no value where its binding was refused, which means it does not exist, where a bound stopped it, where a relation it reads has no value, where it is task-wide over a parameterized table with several constraint models, or, for a `ratio`, where the second relation has no rows.

### The budget of a term

A walk gives each term a budget of 217,039,082,400 cells: twice the greatest charge of any term on the gold tables, so that no term on a gold table passes it. At each ARC example, a term is charged the cells of each relation it reads and the cells of the relation it gives. The cells of a relation are the count of its rows times the count of its columns, whether the relation stands as written rows or as the relations it comes from. The charge depends on the relations alone, and not on how an operator computes the term. A term is charged its inputs before it is evaluated, so a term whose inputs pass the budget is not evaluated, and it is charged its output as it is written, or by its count of rows where the rows stay unwritten. A term whose charges, added over its ARC examples, pass the budget has no value at any of them, and so has each term that reads it. A term that reads a relation which alone passes the budget has no value in the same way.

## Vectors

The [sample contract](../sample-build/contract.md) defines the vectors and their levels. This section gives their holes and how a shape stands for an entry.

| Vector | Holes |
|---|---|
| TableVector | one parameterized table at one assignment, and the base tables |
| QueryVector | the parameterized tables a query uses and the parameterized tables it computes, and the program relations, which ground the table features in the query's text |
| State features | any parameterized tables of a state |

A parameterized table's **upstream tables** are the parameterized tables its query reads, and the parameterized tables those read in turn, down to the base tables, at the same assignment. An upstream table has one of two hole kinds: a **parent**, which the query reads, or an **ancestor**, which it reads through other queries. A shape with such a hole is a QueryVector entry. A TableVector is a function of its parameterized table's tables and the base tables, so two parameterized tables of one task with one `TableHash` have one vector.

A vector entry is a **shape**: a ground expression that reads a table, with that table, any upstream table and each of their columns written as a hole. A column's hole is typed by the column's value type. Holes are numbered by first appearance, so the order of a table's columns does not enter. Each ground expression on a table has one shape. One shape has one ground expression for each binding of its holes to that table's columns that the checker accepts. The shape's name is its expression. So a shape has no cost beyond its ground expressions' size, and a version of the library and the registry, and a size, define one set of names for every table. A **list hole** stands for every column of the table that is a key column or has a type of a named set, as over a group's columns, so it has one binding on a table.

A shape's value at an ARC example is the multiset of its ground expressions' values there. With no binding, the shape is at its default. A ground expression that its aggregate leaves with no value, a `ratio` whose second relation has no rows or a `value-set` without exactly one member, is left out of the multiset, and where none is left, the shape has no value. A ground expression that a bound stopped, or that reads a relation with no value, gives the shape no value at that ARC example, since its value could change the shape's.

A vector is sparse. A table gives the entries whose value differs from the default, keyed by name, and the set of names needs no enumeration. An entry's default is its aggregate's value on no rows: `0` or false. An entry with no value, such as one that a bound stopped, a `ratio` whose second relation has no rows or a `value-set` without exactly one member, is stored as that, since it differs from the default. A `ratio` of 0 is at its default, and where the second relation has rows, the `antijoin` in place of the `semijoin` gives 1 less the value, so a share of 0 shows as a share of 1 there.

- A shape gives two numbers at each ARC example: the greatest and the sum of its ground expressions' values. The sum of a `nonempty` is the number of bindings with a row. With one binding, the two are equal. A `ratio` gives the greatest and the least, since a sum of fractions counts nothing. A fraction is exact, so two ARC examples have one value exactly where their fractions are equal.
- A task-wide root gives those two numbers once.
- A per-input root gives them per ARC example and constraint model. Within an ARC example it takes the mean over the constraint models, as the contract gives. The value at an ARC example is the feature's value. A learned model reads it at each ARC example, as [What a learned model reads](export-design.md#what-a-learned-model-reads) gives. The `least`, `mean` and `most` entries, which the encoder combines outside arclog, are a reading for a learned model with one feature vector per candidate: over the train ARC examples where the expression has an `output` leaf, and over every ARC example otherwise. They lose which value of one entry goes with which value of another at an ARC example.
- A `value-set` over one number column gives a number where the set has one member, and no value otherwise. `Order`'s `maximal` and `minimal` give such a column. Another `value-set` is no vector entry, and it is for a consumer that reads a set.
- In a QueryVector, a hole's type can also state the column's lineage root, as [What column metadata adds to features](arclog-types.md#what-column-metadata-adds-to-features) gives.
- A task-wide count over the table rows of every ARC example depends on how many ARC examples there are, so a ratio pairs it with that count.
- Aggregates over assignments are as the contract gives them: symmetric functions of the vectors, outside arclog. Assignments are not columns.

### State features

A state shape reads two tables of a state, T and U, with each table and each of its columns written as a hole, numbered by first appearance over both. Two columns can meet where their types can, and two Ident columns where they have one source. Its ground expressions come from a named family:

- The rows of each table that the other keeps: `join`, `semijoin`, `antijoin` and `all`, in both directions.
- The value sets of a column of each: `same-values`, and `semijoin` and `all` over each table's `project`.
- The cells of one table inside the boxes of the other: `inside-boxes` and `boxes-holding`.
- The keys of one table whose cells are those of a key of the other, up to a move or also a D4 element: `same-shape` and `same-shape-d4`.
- Two columns that give the output color at a shared cell, where neither does alone: `determines-jointly`.
- The output's cells and the changed cells that T holds, with and without U.

A value stands two ways: at the pair (T, U), and pooled into T over each U by U's relation to T, as the least, the mean and the greatest of its value. At a member of a state, the relations are parent, ancestor, child, descendant and other. At a candidate query over a state, they are parent, ancestor and other.

The state's graph gives its own numbers, each of which counts members, so none depends on the order of a program's forms: a table's depth and its depth below the deepest member, whether it is a root or a leaf, how many tables it reads and how many read it, its ancestors and its descendants, and how many other tables have its rows.

A shape over the base parts that reads no other table stands in a vector of the task's own, at each ARC example. That vector is the same for every candidate of a task, so a comparison of candidates reads it only through what it says together with theirs.

## Program relations

The program itself is data. Base relations reflect it, for the QueryVector. The TableVector reads none of them, since it is a function of its table's rows and the base tables.

| Relation | Contents |
|---|---|
| `query_kind(Q, Kind)` | each query's kind |
| `query_atom(Q, Name)` | each query's atoms, by lib name |
| `query_reads(Q, T)`, `query_computes(Q, T)` | the use edges |
| `column_type(T, C, Type)` | each column's value type |
| `column_source(T, C, Source)` | an Ident column's source |
| `column_frame(T, C, Frame)` | the frames of a place column |
| `column_lineage(T, C, Kind, Upstream)` | each column's lineage |
| `label_site(Q, L, T, C)` | each label's sites, which give a query's joins |

A feature that reads the program text is an arclog query over these relations, in the way program analyses are written in Datalog. A lib name is a new value type with equality alone. The group fixes it, so a lib name may appear as a constant.

## Coverage

**Definition.** Features cover a difference between two databases when at least one feature gives a different value on them. A gap is a difference that no feature sees. A database here is a table, or the tables of one constraint model, with the grids they are read against, at one of two levels:

| Level | Table | Database | Features |
|---|---|---|---|
| One ARC example | no Example column | one table at that ARC example, its input and its train output | per input |
| The task | one constraint model at every ARC example | its tables at every ARC example, every input and every train output | task-wide |

Two databases are compared under one schema: column names, types, sources and frames. A different schema shows in which expressions the checker accepts.

A **symmetry** is an element of D4 and a color permutation, with a bijection of Idents per source and a bijection of poses per assembly. At the level of the task, it also has a reorder of the train pairs and a reorder of the test inputs. Where a ground expression of that level can remake a maker's output from the leaves, an Ident in that output's rows on the database moves by the bijection that the symmetry induces on contents, since the feature can join the table's Idents and read what they label. Any other Ident moves by any bijection onto the Idents outside those rows.

Under a symmetry, a feature that exports numbers alone keeps its value. So full coverage means that every difference other than a symmetry is seen by such a feature.

**The guarantee.** Take, at either level, the ground expressions that export numbers alone, whose leaves are the table, the grids, lib relations and proposers. A program relation is left out, since two programs can compute one database. At unbounded size, these features are a complete invariant of a database: two databases have equal values on all of them exactly where a symmetry relates them.

This needs:

- Ident sources on, and no `Open` Ident column.
- Every lib element being equivariant.
- Numbers read as exact integers, with no cap that stops a computation.

If a symmetry relates two databases, their values are equal. The program is equivariant under the symmetry, and a feature reads any other Ident, and any pose, by equality alone. The proof of the other direction follows.

**The structure of a database** is a finite many-sorted relational structure over the values that occur. A sort is a value type with the types under it, and each Ident source and each pose assembly has its own sort. Its relations are:

- the table's rows
- the grids
- `margin`, over the places that occur
- the lib relations over the orientation types, which are finite
- the rows of each maker's output that a ground expression of that level can remake from the leaves
- one unary relation per number that occurs in either database, true of that number alone, so the two structures have one finite signature

**The proof.** A full conjunctive query is a conjunction of atoms, each with a label at every column, with no `NOT`, `OR`, `IF`, `ALL`, `!=` or order test.

1. A full conjunctive query's rows are the homomorphisms from its body into the structure.
2. By Lovász's theorem, two finite relational structures of one signature are isomorphic exactly where every pattern has the same number of homomorphisms into each. It is stated for one relation, and its proof carries over to a finite signature: the counts of homomorphisms give the counts of injective homomorphisms, by inversion over a pattern's quotients, and an injective homomorphism each way between finite structures is an isomorphism. A label at columns of two sorts has no homomorphism in either structure, and neither has a label at a `Dir` and a `DiagDir` column, or at an `Axis` and a `DiagAxis` column, since those values never coincide. So the patterns that matter give each label values that can coincide. Every value occurs in a relation, so no pattern needs a label outside an atom.
3. A ground expression reaches each such pattern and its count:
    - A table or grid atom is a `join`, a lib atom is a `lib-join`, or a `join` with a lib relation leaf, and a remade maker's atom is a `join` with a `component`.
    - A label repeated in one atom is a `select` with `=`.
    - A place label at a `Position` and an `Offset` column is a `lib-join` with `relative` and a `select` of `X_rel` with `=` and `0`, since the checker refuses one label at both columns.
    - A place that only `margin` reads comes from a `union` of `project`s over the place columns.
    - The unary relations of numbers become key columns. `Cardinality` keyed by the pattern's number labels gives a count at each number, and a `value-set` gives them all. A number with no row has the count 0.
4. An isomorphism of two such structures is a symmetry:
    1. Each number maps to itself, by its unary relation.
    2. The edges map by an element g of D4, since `opposite` must be kept, and the bijections of the four edges that keep opposite pairs are exactly the elements of D4.
    3. Each place maps by g's `apply`, since `margin` must be kept, and a place's margins determine it.
    4. The other orientation values map by g's action, since their lib relations determine them from the edges.
    5. The colors that occur map by a bijection, which extends to a color permutation.
    6. The Idents in the rows of a remade output map by the bijection that the symmetry induces, since those rows must be kept, and they determine what each Ident labels. Any other Ident, and the poses of each assembly, map by a bijection.
    7. At the level of the task, the ARC examples map by a bijection. It keeps train pairs and test inputs apart, since only a train pair has output rows.

    So the rows of one table are the rows of the other under a symmetry.

**What this does not say.**

- The guarantee is about ground expressions. A vector entry combines over bindings and ARC examples, so it sees less. It loses which value of one entry goes with which value of another at an ARC example, and `ratio` keeps that pairing for two counts.
- At the level of the task, a parameterized table with several constraint models at an ARC example has no value, so its constraint models stay unseen there.
- The proof reads `join`, `lib-join`, `select`, `project`, `union`, `Cardinality` and `value-set`. So every other operator adds nothing at unbounded size. Connectivity, Flood, `semijoin`, `antijoin` and `all` lower the size at which a difference appears, and a feature expression's size does not measure pattern size for them. A `ratio` is a function of two `cardinality` values.
- The guarantee needs patterns as large as the data. At a fixed size, different databases can stay unseen, and a separation check is how they are found.
- Seeing a difference is not usefulness. A digest of the whole table would have full coverage and teach a learned model nothing. Coverage is necessary and not sufficient.

## Computational limits

- Every operator of the grammar takes polynomial time on the data, since a relation has no recursion and the lib's closures and detectors are polynomial. So a feature expression of fixed size does too. A table that a solver computes through `CHOOSE`, `ONE` or `Unfold` costs what it costs to evaluate, and an expression reads it per constraint model.
- The number of feature expressions grows exponentially with size, and the complete family is infinite, so size stays a parameter. The cost of a table's encoding grows with its distinct non-empty relations and their extensions, and not with the number of names.
