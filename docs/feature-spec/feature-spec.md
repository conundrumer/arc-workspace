# Feature specification (draft)

The rules for the handwritten encoder from tables to features. The reader is whoever decides this design, and then whoever implements it. [Arclog column types](arclog-types.md) gives what the engine knows about a column, which the features read.

## The objects

| Object | What it is |
|---|---|
| **Feature query language** | The set of all feature expressions: relational algebra with aggregates, lib joins and components. The grammar under "The generating set" defines it. |
| **Feature expression** | One feature as a tree of operators, with holes for a table and its columns. |
| **Ground expression** | A feature expression with its holes bound. Its value is what the encoder computes. |
| **Shape** | A ground expression with its table and that table's columns written as typed holes. It names one entry of a vector for every table. |
| **Generating set** | The primitives that feature expressions are made of. |
| **Feature library** | The written arclog source of the named compositions: one new file, `engine/lib/features.arclog`. |
| **Encoder** | The function that the library defines at a size: from a state's tables to the values of the features that the library names and of every ground expression up to that size. |
| **Feature specification** | This document. It stands to the feature library as the lib specification stands to the lib. |

## Purpose

Features support the program search and do not replace it. A feature expression has the form of a query, so a ground expression of size d shows the model what a query of that size would compute. An encoder run at a size large enough to reach the output would be the search itself, done by brute force. The size to run is set later, from data.

## Definition

- A **feature** is arclog: forms that read tables of a state and base tables, and an `EXPORT` form that says what they give.
- A solver extracts what it needs from a task in arclog, so arclog can state what a feature extracts. A feature is a solver's fragment with `EXPORT` in place of `OUT`.
- Feature forms run after the state's queries and are not added to the state. A model never reads them as part of a program.
- A feature's value is taken at one assignment, and a per-input value at one model. Arclog's own rules say how often a form runs: a `RULE` per input, a `DET` once for a task, and an instance of a component by what its bodies read.

## What the language gives by construction

Each of these follows from the arclog rules, so no feature code and no check repeats it. A row marked "ran" was also tested on the engine.

| Property | Source |
|---|---|
| Independent of the order of rows, columns and atoms | A relation is a set of rows. A column has no order. |
| No test output is read | `output` and `ex_output` contain train outputs alone. `ex_input` contains the test inputs too. |
| A color and a number never join | The checker (ran). |
| Order tests apply to numbers alone | The checker (ran). |
| No literal of a task type, and no number but `0` | The grammar (ran). |
| An Ident joins only within its source | The checker (ran). |
| Two Positions of different extents are never equal | A Position's margins on each axis sum to the extent less one. In grids of equal extents, Positions can be equal, which is a correspondence between the two grids. A Box's value does not determine its frame, as [Frames](arclog-types.md#frames) gives. |
| No free choice in the lib | The lib's obligations in the equivariance document. |
| Equivariance under D4 and the color permutations | The equivariance document: each query is joins, projections, unions and negations, order tests apply to numbers alone, and `0` is the one constant. |

## Transformation law

The program is equivariant, and the group acts on a row column by column. So the type of each exported column gives the feature's transformation law under the group, and the checker can compute it.

| Exported column | Under the group | Law |
|---|---|---|
| none, a number, `Unit`, `Example`, a lib name | fixed | invariant |
| `Color`, `Ident`, an orientation type, `Position`, `Box`, `Offset` | moved by the type's action | equivariant |
| `Pose` | not observable | refused, by a check to add |

Both invariant and equivariant values are features. A consumer that needs invariant values reads the invariant ones.

A reorder of the examples is separate from the group. It moves a per-input value with its example, and it moves an `Example` column. A task-wide value with no `Example` column keeps its value.

The group also moves the assignment, so a value at an assignment corresponds to the value at that assignment's image. A parameterized table's walk over its assignments stops at a cap, and which assignments it reaches depends on an order of encodings. So a pool over a capped walk has no value, and the AssignmentVector's `capped` entry states this.

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
- `output`: the train output of the current example, with the columns `P` and `Col`. It has no rows on a test input. So a per-input feature can compare a table with the output of its own example, at each model.

### Aggregates

The root is one aggregate over a relation.

| Aggregate | Value | On no rows |
|---|---|---|
| `nonempty` | whether the relation has a row | false |
| `cardinality` | its count of rows, over all its columns | 0 |
| `value-set` | the set of the values of its columns | the empty set |
| `ratio` | the first relation's count of rows over the second's, as an exact fraction | 0 where the first has no rows, and no value where the second has none |

Everything else is an operator under one of these. The number of distinct values of `x` is `(cardinality (project R x))`. The share of `R`'s rows that `S` matches is `(ratio (semijoin R S ...) R)`. Whether `x` determines `y` is whether `(ratio (component Singleton (member R (x) (y)) value) (project R x))` is 1. Whether one count is above, at or below another is whether their ratio is above, at or below 1. The greatest group size is a `value-set` over `Order`'s `maximal`.

`ratio` is a root because a vector combines each entry over the examples on its own, which loses which value of one entry goes with which value of another at an example. Examples differ in scale, and a count changes with scale. A ratio of two counts is what stays fixed, so an invariant across examples of different sizes can show only there.

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

An expression is **task-wide** where a leaf has an Example column (`ex_input`, `ex_output`, or a table with one), or is a proposer, since a proposer reads every example. Its `QUERY` forms expand to `DET`. Every other expression is **per input**, and its `QUERY` forms expand to `RULE`.

In a task-wide expression:

- A per-input table is read in its lifted form, with a column `E`. `input` is read as `ex_input`, and `output` as `ex_output`.
- A lifted read gives the label `E` to the Example column, so it cannot read a table's own column named `E`. The expansion first copies that table by a `RULE`, with that column under `E_2`.
- `E` is a column like any other. A binary operator pairs it only where its pairs list it, so a `join` without that pair compares one example with another, and has `E` and `E_2`.
- A macro states no pairs. So its atom on a grid hole has a site on `E` that joins the `E` of the macro's relation, and it reads that example's grid.
- A `component` pools over the examples unless `E` is among its key columns, and a `project` that leaves out `E` pools too. An input's body keeps a site on `E` where its binding leaves `E` out, since a body that reads a per-input table with no such site makes the instance per input.
- A lifted read of `ex_input` contains the test inputs, and `ex_output` contains train outputs alone. So an `antijoin` with `ex_output` keeps every row of a test input.
- On a table with several models, the expression has no value, since no one table stands for every example. A `DET` that reads such a table gives a fault when it runs.

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

- No selected column: whether the relation has a row (ran).
- Several atoms: the product of their projections, as a two-atom `OUT` gives. A `ratio` exports its two counts, each from its own atom, so arclog divides nothing. The encoder reduces the two to lowest terms outside arclog, which gives the exact fraction.
- No feature compares a number with a literal. It exports the number.

So `0` and "no value" differ. `cardinality` gives `0` on no rows. A ground expression has no value where its binding was refused, which means it does not exist, where a bound stopped it, where it is task-wide over a table with several models, or, for a `ratio`, where the second relation has no rows.

## Vectors

The sample contract defines the vectors. This section gives their holes and how a shape stands for an entry.

| Vector | Holes |
|---|---|
| TableVector | one table at one assignment, and the base tables |
| QueryVector | the tables a query uses and the tables it computes, and the program relations, which ground the table features in the query's text |
| Candidate block of a token | the successor body's table and the current body's table, paired by assignment and input, and the program relations of the partial query |
| State features | any tables of a state |

A table's **upstream tables** are the tables its query reads, and the tables those read in turn, down to the base tables, at the same assignment. An upstream table has one of two hole kinds: a **parent**, which the query reads, or an **ancestor**, which it reads through other queries. A shape with such a hole is a QueryVector entry. A TableVector is a function of its table's rows and the base tables, so two tables of one task with one `TableHash` have one vector.

A vector entry is a **shape**: a ground expression that reads a table, with that table, any upstream table and each of their columns written as a hole. A column's hole is typed by the column's value type. Holes are numbered by first appearance, so the order of a table's columns does not enter. Each ground expression on a table has one shape. One shape has one ground expression for each binding of its holes to that table's columns that the checker accepts. The shape's name is its expression. So a shape has no cost beyond its ground expressions' size, and a version of the library and the registry, and a size, define one set of names for every table. A **list hole** stands for every column of the table that is a key column or has a type of a named set, as over a group's columns, so it has one binding on a table.

A shape's value at an example is the multiset of its ground expressions' values there. With no binding, the shape is at its default.

A vector is sparse. A table gives the entries whose value differs from the default, keyed by name, and the set of names needs no enumeration. An entry's default is its aggregate's value on no rows: `0`, false or the empty set. An entry with no value, such as one that a bound stopped, is stored as that, since it differs from the default. A `ratio` is the exception: one with no rows in its second relation is left out, since that relation's `nonempty` states it. A `ratio` of 0 is at its default, and where the second relation has rows, the `antijoin` in place of the `semijoin` gives 1 less the value, so a share of 0 shows as a share of 1 there.

- A shape gives two numbers at each example: the greatest and the sum of its ground expressions' values. The sum of a `nonempty` is the number of bindings with a row. With one binding, the two are equal. A `ratio` gives the greatest and the least, since a sum of fractions counts nothing. A fraction is exact, so two examples have one value exactly where their fractions are equal.
- A task-wide root gives those two numbers once.
- A per-input root gives them per example and model. Within an example it takes the mean over the models, as the contract gives. The value at an example is the feature's value. A model with fixed columns reads `:min`, `:mean` and `:max` entries, which the encoder combines outside arclog: over the train examples where the expression has an `output` leaf, and over every example otherwise. These entries are one way to read the values, and they lose which value of one entry goes with which value of another at an example.
- A `value-set` over one number column gives a number where the set has one member, and no value otherwise. `Order`'s `maximal` and `minimal` give such a column. Another `value-set` is no vector entry, and it is for a consumer that reads a set.
- In a QueryVector, a hole's type can also state the column's lineage root, as [What column metadata adds to features](arclog-types.md#what-column-metadata-adds-to-features) gives.
- A task-wide count over the rows of every example depends on how many examples there are, so a ratio pairs it with that count.
- Pools over assignments stay as the contract gives them: symmetric functions of the vectors, outside arclog. Assignments are not columns.

## Program relations

The program itself is data. Base relations reflect it, for the QueryVector and the candidate block. The TableVector reads none of them, since it is a function of its table's rows and the base tables.

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

**Definition.** Features cover a difference between two databases when at least one feature gives a different value on them. A gap is a difference that no feature sees. A database here is a table with the grids it is read against, at one of two levels:

| Level | Table | Database | Features |
|---|---|---|---|
| One example | no Example column | one model's rows at that example, its input and its train output | per input |
| The task | one model at every example | its rows at every example, every input and every train output | task-wide |

Two databases are compared under one schema: column names, types, sources and frames. A different schema shows in which expressions the checker accepts.

A **symmetry** is an element of the group, with a bijection of Idents per source and a bijection of poses per assembly. At the level of the task, it also has a reorder of the train pairs and a reorder of the test inputs. Where a ground expression of that level can remake a maker's output from the leaves, an Ident in that output's rows on the database moves by the bijection that the symmetry induces on contents, since the feature can join the table's Idents and read what they label. Any other Ident moves by any bijection onto the Idents outside those rows.

Under a symmetry, an invariant feature keeps its value, and an equivariant feature moves by the group's action. So full coverage means that every difference other than a symmetry is seen by an invariant feature.

**The guarantee.** Take, at either level, the ground expressions that export numbers alone, whose leaves are the table, the grids, lib relations and proposers. A program relation is left out, since two programs can compute one database. At unbounded size, these features are a complete invariant of a database: two databases have equal values on all of them exactly where a symmetry relates them.

This needs:

- Ident sources on, and no `Open` Ident column.
- Every lib element meeting its equivariance obligation.
- Numbers read as exact integers, with no cap that stops a computation.

If a symmetry relates two databases, their values are equal. The program is equivariant under the group with the induced bijection, and a feature reads any other Ident, and any pose, by equality alone. The proof of the other direction follows.

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
    7. At the level of the task, the examples map by a bijection. It keeps train pairs and test inputs apart, since only a train pair has output rows.

    So the rows of one table are the rows of the other under a symmetry.

**What this does not say.**

- The guarantee is about ground expressions. A vector entry combines over bindings and examples, so it sees less. It loses which value of one entry goes with which value of another at an example, and `ratio` keeps that pairing for two counts.
- At the level of the task, a table with several models at an example has no value, so its models stay unseen there.
- The proof reads `join`, `lib-join`, `select`, `project`, `union`, `Cardinality` and `value-set`. So every other operator adds nothing at unbounded size. Connectivity, Flood, `semijoin`, `antijoin` and `all` lower the size at which a difference appears, and a feature expression's size does not measure pattern size for them. A `ratio` is a function of two `cardinality` values.
- The guarantee needs patterns as large as the data. At a fixed size, different databases can stay unseen, and a separation check is how they are found.
- Seeing a difference is not usefulness. A digest of the whole table would have full coverage and teach a model nothing. Coverage is necessary and not sufficient.
- It does not limit what a feature exports.

## Additions to arclog

Each is ours to add. These need a new reader for the library's file and changes in the checker. The registry's `macro` form defines lib relations and its `proposer` form gives bodies, and neither takes these forms.

- `fragment`, `feature`, `QUERY` and `EXPORT`, with holes, the splices and `gives`.
- The leaf `output`, for feature forms alone. `output` stands where `input` stands in the rule that gives an instance's level, in the check of what a form reads, and in the frames, where its `P` stands in the current example's output.
- The program relations as base relations, and the lib name type, whose constants are lib names.
- A check that refuses a `Pose` at an exported column. The pose rule lets a derived column take one, and a frame change moves it.

## Worked expansions

Each ran with no change to the language, with sources on, at the end of solver 25d487eb or of the solver it names, through `scripts/arclog.py rows`, with a plain `RULE` or `DET` in place of `EXPORT`. A list of counts is in the order of the train examples, then the test input.

**`(cardinality (project &ink Col))`.** It gives 2 at each input.

```lisp
(RULE &p (&ink *Col))
(INIT &f1 Cardinality
  (member ((:m Col))
    (&p *Col)))
(RULE &v (&f1.size *N))
```

**`(cardinality &ink)`, over whole rows.** It gives 9, 16, 9, 16.

```lisp
(INIT &s Cardinality
  (member ((:m P Col))
    (&ink *P *Col)))
(RULE &v (&s.size *N))
```

**`(join &mark input (P P))`, which `(join-label &mark P input)` writes.** It gives 1 row at each input.

```lisp
(RULE &q
  (&mark *P *Col)
  (input P (:Col *Col_2)))
```

**`(join (join &ink input (P P)) input (P P))`, which two calls of `join-label` write.** It gives 9, 16, 9, 16 rows, with `Col`, `Col_2` and `Col_3`.

```lisp
(RULE &q1
  (&ink *P *Col)
  (input P (:Col *Col_2)))
(RULE &q2
  (&q1 *P *Col *Col_2)
  (input P (:Col *Col_3)))
```

**`(join &rays.ray input (Origin P))`, which `(join-label &rays.ray Origin input)` writes.** It gives 12, 9, 13, 15 rows.

```lisp
(RULE &q
  (&rays.ray *Origin *P *D *K)
  (input (:P Origin) *Col))
```

**`(join (component Cardinality (member &ink (P) (Col)) size) input (P P))`, which `(join-label (group-sizes &ink P) P input)` writes.** It gives 9, 16, 9, 16 rows, with `P`, `N` and `Col`.

```lisp
(INIT &c Cardinality
  (key ((&ink ^P))
    (member ((:m Col))
      (&ink P *Col))))
(RULE &sizes (&c.size (:key *P) *N))
(RULE &q
  (&sizes *P *N)
  (input P *Col))
```

**`(lib-join &mark margin (B P))`.** It gives 4 rows at each input, one per direction.

```lisp
(RULE &q
  (&mark *P *Col)
  (margin (:B P) *D *K))
```

**`select`, over `(lib-join (project &ink P) dist_pair (P P))`.** `(select &d K = K2)` gives 0, 0, 0, 6 rows, and `(select &d K > K2)` gives 18, 32, 18, 29. `(select &rays.ray K = 0)` gives 1 row at each input. Each `Op` ran with a column and with `0`. The same `=` written as `(= K K2)` or `(= K 0)` beside the read is refused: "a site of the list makes the label, so the site names its partner".

```lisp
(RULE &p (&ink *P))
(RULE &d
  (&p *P)
  (dist_pair P *D *K *K2))
(RULE &equal (&d *P *D *K (:K2 K)))
(RULE &greater
  (&d *P *D *K *K2)
  (> K K2))
(RULE &start (&rays.ray *P *D (:K 0) *Origin))
```

**`(cardinality (component Singleton (member &ink (P) (Col)) plural))`.** It gives 0 at each input, so `P` determines `Col`.

```lisp
(INIT &f2 Singleton
  (key ((&ink ^P))
    (member ((:v Col))
      (&ink P *Col))))
(RULE &o (&f2.plural (:key *P)))
(INIT &n Cardinality
  (member ((:m P))
    (&o *P)))
(RULE &v (&n.size *N))
```

**`(component Singleton (member (join &mark input (P P)) (Col) (P Col_2)) value)`, a type parameter of two columns.** The port's columns are `Col`, `P` and `Col_2`. It gives 1 row at each input.

```lisp
(RULE &q
  (&mark *P *Col)
  (input P (:Col *Col_2)))
(INIT &f3 Singleton
  (key ((&q ^Col))
    (member ((:v P Col_2))
      (&q Col *P *Col_2))))
(RULE &o (&f3.value (:key *Col) (:v *P *Col_2)))
```

**The histogram and the greatest of group sizes.** `(component Cardinality (member &ink (Col) (P)) size)` gives `&sizes`. `(component Cardinality (member &sizes (N) (Col)) size)` gives the histogram, with its count at `N_2`: (1, 1), (8, 1) at the first input. Two calls of `group-sizes` write these. `(component Order (member (project &sizes N) () (N)) (score (project &sizes N) () (N N)) maximal)` gives 8 at the first input.

```lisp
(INIT &c1 Cardinality
  (key ((&ink ^Col))
    (member ((:m P))
      (&ink Col *P))))
(RULE &sizes (&c1.size (:key *Col) *N))
(INIT &c2 Cardinality
  (key ((&sizes ^N))
    (member ((:m Col))
      (&sizes N *Col))))
(RULE &histogram (&c2.size (:key *N) (:N *N_2)))
(RULE &ns (&sizes *N))
(INIT &o Order
  (member ((:t N)) (&ns *N))
  (score ((:t N) (:S N)) (&ns *N)))
(RULE &greatest (&o.maximal (:t *N)))
```

**`(component Cardinality (member (project &ink Col) (Col) ()) size)`, a binding with no column.** It gives 1 for each color. The head `((:m))` is refused: "a site holds a label or a field site".

```lisp
(RULE &p (&ink *Col))
(INIT &c Cardinality
  (key ((&p ^Col))
    (member ()
      (&p Col))))
(RULE &sizes (&c.size (:key *Col) *N))
```

**`(component Cardinality (member &body_count.size (N) (Col)) size)`, a table with a key.** It gives (1, 1), (8, 1) at the first input.

```lisp
(INIT &c Cardinality
  (key ((&body_count.size ^N))
    (member ((:m Col))
      (&body_count.size (:key *Col) N))))
(RULE &sizes (&c.size (:key *N) (:N *N_2)))
```

**`(component Cardinality (member &mark (Col) (P)) (domain &ink (Col)) size)`, two bindings with key columns.** A key that `&ink` alone has counts 0. It gives (1, 1), (0, 2) at the first input, and with a key clause over `&mark` alone it gives (1, 1).

```lisp
(INIT &c Cardinality
  (key ((OR ((&mark ^Col)) ((&ink Col))))
    (member ((:m P))
      (&mark Col *P))
    (domain ()
      (&ink Col))))
(RULE &sizes (&c.size (:key *Col) *N))
```

**`(component Excess (plus &ink () (P Col)) (minus &marks () (Origin Col)) excess)`, two bindings of a record.** It gives 8, 15, 8, 15. The head `((:m Origin Col))` gives a fault when it runs.

```lisp
(RULE &origins (&rays.ray *Origin))
(RULE &marks
  (&origins *Origin)
  (input (:P Origin) *Col))
(INIT &e Excess
  (plus ((:m P Col))
    (&ink *P *Col))
  (minus ((:m (:P Origin) Col))
    (&marks *Origin *Col)))
(RULE &o (&e.excess *N))
```

**`(ratio &mark &ink)`.** The two counts are (1, 9), (1, 16), (1, 9), (1, 16), so the values are 1/9, 1/16, 1/9, 1/16.

```lisp
(INIT &a Cardinality
  (member ((:m P Col))
    (&mark *P *Col)))
(INIT &b Cardinality
  (member ((:m P Col))
    (&ink *P *Col)))
(RULE &v (&a.size *N) (&b.size (:N *N_2)))
```

**`(ratio (component Singleton (member &ink (P) (Col)) value) (project &ink P))`.** The two counts are (9, 9), (16, 16), (9, 9), (16, 16), so the value is 1 at each input, and `P` determines `Col`.

```lisp
(INIT &f Singleton
  (key ((&ink ^P))
    (member ((:v Col))
      (&ink P *Col))))
(RULE &one (&f.value (:key *P)))
(RULE &cells (&ink *P))
(INIT &a Cardinality
  (member ((:m P))
    (&one *P)))
(INIT &b Cardinality
  (member ((:m P))
    (&cells *P)))
(RULE &v (&a.size *N) (&b.size (:N *N_2)))
```

**`(semijoin &ink &mark (P P))`.** It gives 1 row at each input.

```lisp
(RULE &q
  (&ink *P *Col)
  (&mark P))
```

**`(nonempty (all &ink input () (P P) (Col Col)))`.** It is true at each input. `(nonempty (all &ink &mark () (P P)))` is false at each input.

```lisp
(RULE &v
  (ALL ((&ink *P *Col)) ((input P Col))))
```

**`(nonempty (all &none input () (P P)))`, over a domain with no rows.** It is false at each input.

```lisp
(RULE &none
  (&ink *P *Col)
  (margin (:B P) *D *K)
  (< K 0))
(RULE &v
  (ALL ((&none *P)) ((input P))))
```

**`(all &ink &mark (Col) (P P))`, with an outer column.** It gives the colors 1, 3, 2, 8, one at each input. `(antijoin (project &ink Col) (project (antijoin &ink &mark (P P)) Col) (Col Col))` gives the same rows at size 4.

```lisp
(RULE &colors (&ink *Col))
(RULE &v
  (&colors *Col)
  (ALL ((&ink *P Col)) ((&mark P))))
```

**`(component Connectivity (node &ink (Col) (P)) (step step_offset () (V)) component)`, with the eight steps.** It gives 9, 16, 9, 16 rows, with `Col`, `P` and `Id`.

```lisp
(INIT &c8 Connectivity
  (key ((&ink ^Col))
    (node (P)
      (&ink Col *P)))
  (step ((:Delta V))
    (step_offset *V)))
(RULE &o (&c8.component (:key *Col) *P *Id))
```

**The D4 orbits of the cells of a frame, as `(cardinality (project (component Quotient (equivalent &pairs () (P P_out)) class) Id))`.** `&pairs` is a `join` of a `lib-join` of a `join`. On solver 25d487eb it gives 40, 21, 48, 48. On solver 0d3d703e, whose grids are 3x3, it gives 3 at each input: the center, the corners and the edge middles.

```lisp
(RULE &cells (input *P))
(RULE &moved
  (&cells *P)
  (d4_elem *D))
(RULE &images
  (&moved *P *D)
  (apply D P *P_out))
(RULE &pairs
  (&images *P *D *P_out)
  (&cells (:P P_out)))
(INIT &place Quotient
  (equivalent ((:a P) (:b P_out))
    (&pairs *P *P_out)))
(RULE &class (&place.class (:a *P) *Id))
(RULE &ids (&class *Id))
(INIT &classes Cardinality
  (member ((:m Id))
    (&ids *Id)))
(RULE &v (&classes.size *N))
```

**The translation classes of components.** Each step is one operator, and the last is `(cardinality (project &class Id_2))`. It gives 2 at each input.

```lisp
(INIT &comp Connectivity
  (key ((&ink ^Col))
    (node (P)
      (&ink Col *P))))
(RULE &cells (&comp.component (:key *Col) *P *Id))
(INIT &box BoundingBox
  (key ((&cells ^Id))
    (cell (P)
      (&cells Id *P))))
(RULE &boxes (&box.box (:key *Id) *B))
(RULE &joined
  (&cells *Col *P *Id)
  (&boxes Id *B))
(RULE &rel
  (&joined *Col *P *Id *B)
  (relative (:Base B) (:X P) *X_rel))
(INIT &same Inclusion
  (pattern ((:pattern Id) (:m X_rel))
    (&rel *Id *X_rel))
  (observed ((:observed Id) (:m X_rel))
    (&rel *Id *X_rel)))
(RULE &equal (&same.equal (:observed *Id) (:pattern *Id_2)))
(INIT &shape Quotient
  (equivalent ((:a Id) (:b Id_2))
    (&equal *Id *Id_2)))
(RULE &class (&shape.class (:a *Id) (:Id *Id_2)))
(RULE &ids (&class *Id_2))
(INIT &n Cardinality
  (member ((:m Id_2))
    (&ids *Id_2)))
(RULE &v (&n.size *N))
```

**`(select (join &beam ex_output (E E) (P P)) Col != Col_2)`.** A `DET` reads the lifted form. `&j` gives 9, 5, 10 rows at the train examples and none at the test input. `&v` has no rows. `output` is not in the language, so the comparison with `output` ran in this form.

```lisp
(DET &j
  (&beam *E *P *Col)
  (ex_output E P (:Col *Col_2)))
(DET &v
  (&j *E *P *Col *Col_2)
  (!= Col Col_2))
```

**`(cardinality (join &beam output (P P)))`, through `ex_output`.** It gives (0, 9), (1, 5), (2, 10), (3, 0), by `E`.

```lisp
(INIT &c Cardinality
  (key ((ex_input ^E))
    (member ((:m P))
      (&beam E *P)
      (ex_output E P))))
(DET &v (&c.size (:key *E) *N))
```

**`(join ex_input ex_output (P P))` and `(join ex_input ex_output (E E) (P P))`, on solver 0d3d703e.** Its 5 inputs and 4 train outputs have one size. The first gives 180 rows, with `E` and `E_2`. The second gives 36.

```lisp
(DET &across
  (ex_input *E *P *Col)
  (ex_output (:E *E_2) P (:Col *Col_2)))
(DET &within
  (ex_input *E *P *Col)
  (ex_output E P (:Col *Col_2)))
```

**`(join-label &output P ex_output)`, on solver 0d3d703e.** It joins `E` and gives 36 rows. With no site on `E` at `ex_output`, it gives 165.

```lisp
(DET &q
  (&output *E *P *Col)
  (ex_output E P (:Col *Col_2)))
```

**`(antijoin &beam ex_output (E E) (P P) (Col Col))`.** It gives 11 rows, all at the test input.

```lisp
(DET &v
  (&beam *E *P *Col)
  (NOT (ex_output E P Col)))
```

**`(component Cardinality (member &ink (E) (P Col)) size)` and `(component Cardinality (member &ink () (Col)) size)`, in a task-wide expression.** The first gives (0, 9), (1, 16), (2, 9), (3, 16), by `E`. The second, with its site on `E`, gives 5 for the task. With no site on `E`, its instance is per input, and a `DET` over it gives 2.

```lisp
(INIT &by_example Cardinality
  (key ((&ink ^E))
    (member ((:m P Col))
      (&ink E *P *Col))))
(DET &sizes (&by_example.size (:key *E) *N))
(INIT &pooled Cardinality
  (member ((:m Col))
    (&ink *E *Col)))
(DET &colors (&pooled.size *N))
(INIT &per_input Cardinality
  (member ((:m Col))
    (&ink *Col)))
(DET &colors2 (&per_input.size *N))
```

**A table with its own column `E`.** A lifted read of `&x` gives `E` the type `Example`, and `&x`'s colors can't be read. `&y` reads the copy, with `E` an `Example` and `E_2` a `Color`, and gives 50 rows.

```lisp
(RULE &x (&ink *P (:Col *E)))
(RULE &copy (&x *P (:E *E_2)))
(DET &y (&copy *E *P *E_2))
```

**A table with several models, on solver a6953f00.** `&corner` has 2 models at each assignment and input, and the read `(RULE &q (&corner *D))` gives 1 row at each model. This `DET` gives a fault when it runs.

```lisp
(DET &q (&corner *E *D))
```

**The shape `(cardinality (project T ?1))`, with `?1` typed `Color`, on `&output`.** `&output` has two `Color` columns, so the shape has two ground expressions, one for each. Each gives 3 at each input, so the shape's value is the multiset {3, 3}, with greatest 3 and sum 6.

```lisp
(RULE &p1 (&output (:Col_in *X)))
(INIT &i1 Cardinality
  (member ((:m X))
    (&p1 *X)))
(RULE &b1 (&i1.size *N))
(RULE &p2 (&output (:Col *X)))
(INIT &i2 Cardinality
  (member ((:m X))
    (&p2 *X)))
(RULE &b2 (&i2.size *N))
```

**`(cardinality SharedColor)`, on solver 009d5c81.** `&p` gives 0, 1, 8 as one value, and `&v` gives 3.

```lisp
(DET &p SharedColor (SET))
(INIT &c Cardinality
  (member ((:m C))
    (&p *C)))
(DET &v (&c.size *N))
```

**`SharedColor` in the other forms, on solver 009d5c81.** `(DET &p SharedColor)` gives 3 assignments, with 0, 1 and 8. On solver 25d487eb, `(DET &p SharedColor (SET))` gives 0, and `(RULE &p SharedColor)` gives 0, 1, 2 at the first input. A native proposer takes the same forms: `(DET &p RarestColor (SET))`, on solver 070dd51e, gives 3, 8 as one value.

**`(DET &p VanishedColor)` and `(DET &p VanishedColor (SET))`, where the proposer has no row.** With the second form, this read gives 2 rows at each input. With the first, it gives no rows.

```lisp
(DET &p VanishedColor (SET))
(RULE &q
  (&ink *Col)
  (NOT (&p (:C Col))))
```

**`(join &ink ChangedPairs (Col C_to))`, a proposer of two columns.** `&p` gives (0, 1), (0, 2), (0, 3) as one value, and `&j` gives 19 rows. `(DET &p ChangedPairs (SET))` is refused: "a `SET` mark stands only after proposers of one column each that the registry does not mark `domain`, in a clause with no body".

```lisp
(DET &p ChangedPairs)
(DET &j
  (&ink *E *P *Col)
  (&p (:C_to Col) *C_from))
```

## What in the sample contract changes

The contract holds except where this list changes it.

- A feature is defined in arclog. An implementation that runs faster is a separate matter, and it is checked against the definition, as a native lib element is. This replaces "written once in the crate, which has no engine dependency".
- A number from arclog is an integer. A `ratio`'s value is an exact fraction, stored as two integers in lowest terms.
- `names` and `values` become a sparse map from name to value, in place of one list of names and one float per name.
- `types` includes the Ident source, since a shape's bindings depend on it.
- A feature's value at an example is defined per expression, and `:min`, `:mean` and `:max` entries over the examples are added for a model with fixed columns. In the contract, a feature combines over examples as it defines. The aggregates over assignments stay as the contract gives them.
- The rule "where colors tie for the most common, the lowest color is taken" goes, since it is a free choice. Under a tie, `Order`'s `maximal` output contains every tied member.

## Computational limits

- Every operator of the grammar takes polynomial time on the data, since a relation has no recursion and the lib's closures and detectors are polynomial. So a feature expression of fixed size does too. A table that a solver computes through `CHOOSE`, `ONE` or `Unfold` costs what it costs to evaluate, and an expression reads it per constraint model.
- The number of feature expressions grows exponentially with size, and the complete family is infinite, so size stays a parameter. The cost of a table's encoding grows with its distinct non-empty relations and their extensions, and not with the number of names.
