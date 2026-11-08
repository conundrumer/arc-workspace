# Arclog column types

What the engine knows about a column before it reads a table row, written down from the engine's code, which is the source of truth. The reader is whoever designs features over tables, or changes the type check. Each section names the code it comes from.

## Column metadata

A column has four static facts. A table row contains none of them: a table row is a fixed-arity array of 32-bit term ids, and the checker holds the types.

| Fact | Says | Where |
|---|---|---|
| **Value type** | what kind of value the column contains, and what may be done with it | `arclog/src/types/lattice.rs` |
| **Source** | for an Ident, which form made it | `arclog/src/types/ident_source.rs` |
| **Frames** | which grids its Position or Box values stand in | `arclog/src/check/frames.rs`, `arclog-tables/src/flows.rs`, `arclog/src/registry/frames.rs` |
| **Column lineage** | which upstream columns its values come from, and how; the engine's code calls this its flows | `arclog-tables/src/flows.rs` |

The value type and the source are one thing in the code, since the source is a field of the Ident type. The check refuses a program by them. Frames narrow types only where a lib relation's rule reads them, and lineage refuses nothing.

## Value types

| Type | Directly under | Values | The group's action | Order | Has `0` | Has a frame |
|---|---|---|---|---|---|---|
| `Int` | | signed 32-bit | none | yes | yes | |
| `Nat` | `Int` | whole numbers from 0 | none | yes | yes | |
| `Color` | | a constant | the color permutation | | | |
| `Example` | | an ARC example's index | none, and a reorder of the train pairs moves it | | | |
| `Unit` | | one value, with no fields | none | | | |
| `Box` | | four margins (t, b, l, r) | `apply` | | yes | yes |
| `Position` | `Box` | a box of one cell | `apply` | | yes | yes |
| `Offset` | `Box` | a box whose margins on each axis sum to 0 | `apply` | | yes | |
| `Ident` | | the label of a content, with no source | the bijection the group induces on contents | | | |
| `Ident(source)` | `Ident` | the same, from one maker | the same | | | |
| `D4` | | the eight symmetries | conjugation | | | |
| `C4` | `D4` | the four turns | conjugation | | | |
| `Dir8` | | an edge or a corner | the action on directions | | | |
| `Dir`, `DiagDir` | `Dir8` | edges, corners | the same | | | |
| `Axis4` | | an axis or a diagonal | the swap the directions induce | | | |
| `Axis`, `DiagAxis` | `Axis4` | axes, diagonals | the same | | | |
| `Sym` | | a subgroup of D4 | conjugation | | | |
| `Sense` | | two senses of a turn | a reflection reverses it, a rotation keeps it | | | |
| `Pose(assembly)` | | a pose of one `RIGID_DET` assembly | none that a read can see, since the engine's choice of frame moves it; `pose_difference` gives a D4 value, which the group moves by conjugation | | | |
| `Record(fields)` | | what a key, or a type parameter of several fields or of none, binds to; each field takes a column | field by field | | | |

The action column is from the equivariance document. The rest is from `lattice.rs`.

### The lattice

A type A is **below** B when A equals B or B is A's parent.

- **Meet:** the lower of two comparable types. Otherwise the meet is empty, and a label of both types has no value.
- **Join:** the upper of two comparable types, or their common parent. Two Ident types of different sources have no join, although both stand under `Ident`. Otherwise there is no join.

So `Position` and `Offset` have an empty meet and the join `Box`. `Dir` and `DiagDir` have an empty meet and the join `Dir8`.

### How a label gets its type

From `arclog/src/types/label_walk.rs` and `arclog/src/check/inference.rs`:

- A label's type is the meet of the types of its sites, other than those of `NOT` atoms. Where those give no type, it is the meet over its `NOT` sites.
- A `NOT` site whose type has an empty meet with another site's type is a fault.
- `OR` gives the join over its branches. `IF` gives the meet of its test with the join of its then and its else. `ALL` gives the meet of its domain and its body.
- A constraint over two labels gives each the other's sites. `0` gives no type.
- A bounded type parameter binds to the join of the types of its projections, and that type stands at or under the bound. An unbounded one takes the type of its first projection, and a later projection whose type has an empty meet with it is refused.
- A lib relation's `(types ...)` rules narrow a `Box` column from the types of the labels at its other columns and, through `same-frame`, from their grids. For example, `relative` gives `Offset` where `Base` and `X` are Positions in one frame.

### What each type permits

- **Equality** is defined on every type that a label can have: any label can join two sites whose meet is not empty. No label has a Record type, since a site names the record's fields. The pose rule of the equivariance document limits where a Pose label may stand.
- **Order** is defined on `Int` and `Nat` alone (`admits_order`). An order on any other type would be an order of an encoding.
- **Constants:** `0` alone, on `Int`, `Nat` and the box types (`has_zero`).

## Sources

An Ident has a meaning only with respect to what made it, so the type contains its maker.

- **`Open`:** a declared column with no maker yet, and an Ident read from a file.
- **`Form(id)`:** the one source of the column. The id is a hash of the maker form's resolved content and its output port. So one query has one source in every program, and two forms of one content in one program have one source. A form with no content takes its name and its canonical form in place of the content.

The check gives each maker's Ident output its own source. A join, a `NOT`, an `=` or `!=`, a union or a type parameter that meets two sources is refused. The type name of an Ident column in a TableHash holds the column's source, `Open` or `Form(id)` with the whole id, so two tables whose Ident columns have different sources have different TableHashes, and two tables of equal content whose Ident columns have one source have equal TableHashes. The type names of a table export hold no source; `column_ident_sources` gives it. `column_type_keys` gives the name as the TableHash writes it. The TableHash has a version (`arclog.table_hash_version()`), 3 for this definition.

The intern table keeps a digest of each content, the same in every session. A table export gives the digest's first 32 bits as the Ident's cell. The digest does not contain the maker, so equal contents of two makers have one cell.

No environment variable changes a TableHash or any other result of the engine.

## Frames

A frame says what grid a place stands in. The two checks that read frames work from the same idea, and each has its own form.

- **A grid** (`check/frames.rs`) is the input or the output of one ARC example. The ARC example is the one a per-input form runs on, or the one an Example label holds. A label is in a grid where its value stands in that grid in every table row of the label's form.
- **A source's frame** (`flows.rs`, `SourceFrame`) is one of:
    - `Read`: the frame of the column read.
    - `Made { maker, at, within }`: a frame that a lib column makes, one per table row of the atom or instance at `at`, lying in the frame `within` where that exists.
    - `Unknown`: a frame the engine cannot name, such as where a D4 element moves the values.

**Frame rules** (`registry/frames.rs`, the `frames` forms of the registry) say how a lib column of type `Position` or `Box` gets its frame:

- `(of <column> ...)`: the frame of those columns' values.
- `new`: a frame the column makes.
- `(new (of <column> ...))`: a made frame that lies in the frame of those columns' values.
- A `new` rule on a `Box` column ends in `(size <column> [(by <column>)])`, the column whose values have the own size of the made values.
- A column no form names takes `of` the columns of its type that the mode binds, or, for a component's output, the input columns that its table rows copy, or else its inputs' columns other than `key`.

**What a value determines:**

- A `Position` determines the extents of its frame, since its margins on each axis sum to the extent less one. So two Positions of different extents are never equal.
- A `Box` does not. Equal margins in two frames of different extents give equal values that are different boxes. The check refuses no such join. A `same-frame` condition reads frames only where a lib relation's type rule states one.
- An `Offset` stands in no frame.

## Column lineage

A column's lineage says where its values come from (`flows.rs`, `ColumnSource`). In database theory, a copy is where-provenance. The lineage is computed over the program's dependency graph, as the union over every form, clause and branch that gives the column.

| Kind | The column contains |
|---|---|
| `Copy` | the upstream column's values |
| `Computed` | values the engine computes from the upstream column's |
| `Constant` | `0` |
| `LibName` | values a lib name gives with no program relation read: a proposer's, or a component's default table rows |

An upstream entry also names the relation read, the column, the atom that reads it, which table row of that atom's relation the value comes from, and the frames it gives. Following `Copy` entries back to `input`, `ex_output`, a proposer or a lib column gives a column's **lineage roots**.

The tables export writes the lineage beside each table (`FlowColumns` in `arclog-tables/src/columns.rs`).

## What column metadata adds to features

A join states that two values are equal. The type says whether the statement is allowed. The metadata says what it means.

- **An Ident:** a join across sources means nothing, so the check refuses it. Two forms of one content have one source and make equal Idents. So a feature that remakes a table's maker can join the table's Idents, and read what they label.
- **A color or a number:** a join across lineage roots is allowed, and its meaning depends on the roots. The value type is one `Color` in each of these:
    - `input.Col` with `input.Col` at another cell: two cells of one color.
    - `input.Col` with `ex_output.Col` at one Position: a color the output keeps.
    - `input.Col` with `DominantColor.C`: a cell of the proposed color.
    - `input.Col` at two ARC examples: a color that recurs across ARC examples.
- **A place:** a join within one frame is a statement about one grid. A join across frames of equal extents is a correspondence between two grids.

So a column's metadata acts as a finer type, a refinement of its value type, and it gives features three things:

1. **Aggregates over joins.** For a pair of columns, a feature can state their lineage roots and frames beside what their table rows show. A query's joins can be classified the same way: same root, different roots, same frame, across frames.
2. **Finer holes.** A hole can range over the columns of one kind of metadata, such as the Color columns whose lineage root is `ex_output`.
3. **Global names.** Lineage roots form a finite vocabulary: the base tables' columns and the lib's columns. So a pool over the columns of one kind of metadata has a name that means the same in every task, which a column's identity in one program does not.

Lineage reads the program, so a feature that uses it depends on the computing query, as a QueryVector's features do.
