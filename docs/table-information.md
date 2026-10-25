# Table rows and the information they carry

What the rows of the feature encoder's tables are, how many a table holds at each cut the encoder and the engine have taken, and how much information a row carries. The reader is a session that works on table size: in the encoder, in the lib, or in a solver. [encoder-large-tables.md](encoder-large-tables.md) gives the table cap this work serves and why it exists; [feature-encoder.md](feature-encoder.md) gives the encoder.

## Basis

The tables come from a tables export under `work/tables/`: the engine's derived tables for every case, with the engine's projection cap of 10,000 rows per entry. Evidence tables, faulted tables and tables whose projection search stopped are left out.

A table's rows are what the encoder counts: an entry under the projection cap counts its rows, and an entry over it counts the rows of its maximal projections. Attention cost is the square of a table's rows, and the table cap is 4,000 rows.

The reads of each relation come from each case's token stream, through `arclog.corpus_streams`: a model-written relation token is a read, and the column tokens of its sites are the columns read. In an `INIT`, `CHOOSE` or `RIGID_DET` form, a read of a per-input relation puts the Example column at position 0, and a read of an instance relation whose key was skipped puts the key at the first position, so those positions are dropped. A read position outside a table's columns is ignored.

The scripts are under [table-information/](../work/table-information/): `pertable.py` builds the per-table rows at each stage and writes `<export>_split.parquet` and `<export>_whole.parquet`; `tail.py`, `snr.py`, `factor.py` and `ports.py` read them. They run with `work/lm/.venv/bin/python`. Run `pertable.py` with `EXPORT=<export under work/tables/>` and `STREAMS=<streams export under work/lm/>`, made at the same master as the tables export. The numbers of an export are what these scripts print; this document holds none.

## Rows per table at each stage

Each stage includes the ones before it:

1. One table per relation.
2. One table per assignment, as the encoder reads them (`lm/encoder.py`).
3. Stage 2 minus the engine's one-atom input cut (C20-73), which keeps an input whose atom reads a lib relation. An engine with that cut already has this stage at stage 2.
4. Clause tables projected onto the columns read.
5. Instance outputs projected too.

Stages 4 and 5 assume knowledge of every later read, which a live decode does not have, so they are ceilings.

The split per assignment is the move that changes the tail: a relation with several assignments becomes several tables, each under its own cap.

Information grows with rows and attention cost with rows squared, which is why the cap pays and why cuts that keep every bit and shrink rows are free.

## Information per row

For each per-assignment table over 1,000 rows at stage 5, on its largest entry that holds rows: the key is the fewest columns that determine a row, and the key's domain is the product of the distinct values each key column holds. Two bounds per row:

- lower: log₂(domain ÷ rows), the bits to say which key tuples are present given the value sets;
- upper: the lower bound plus log₂ of the distinct count of each non-key column, as if nothing determined those values.

A table is a cross product when its rows are at least 90% of the key's domain, a function when its key is one column of several, sparse when its rows are under 10% of the domain, and dense otherwise.

The measure has a blind spot: it rates a table against its own value sets, not against the grid and the program. A set of cells keyed by one column scores 0 bits though which cells it holds is information relative to the grid, and a table that repeats another table scores whatever that table scores. The cross-product class is overstated for the same reason: tables that are exactly a product of their factors, where the factors replace the rows, cut only 10% of the rows of the tables over 1,000 (`factor.py`); most of the class is sets of cells with attributes.

### Idioms with zero information per row

Ways a solver spells out a structure whose every row the grid or another table implies:

| input | how the site writes it | the form that carries the same information |
| --- | --- | --- |
| Distance.edge, Propagation.edge | the grid's adjacency inside a node set: `occluder(Q), dir_elem(D), neighbor(Q, D, Q2), occluder(Q2)` | CellDistance and Flood, the lib's cell instances of Distance and Propagation: n rows of Box in place of 4n rows of Box×Box |
| Propagation.edge | every pair with `N2 < N`, then closed | Order's score form, which materializes no pairs |
| Propagation.edge | Distance's `predecessor` joined to a key | the composition as written; a one-atom `edge` has no table since 20-73, and a path output on Distance would name a composition, which [lib-spec.md](lib-spec.md) forbids |
| Ray.node | a guard with no variable, times `input` | `input` alone, which 20-73 cuts: when the guard fails, `dir` is empty and the ray casts nothing |

The lib-spec principle that covers these: Order takes a score in place of the pairs it induces, Quotient takes a generating `edge` beside `equivalent`, and Flood and CellDistance are Propagation and Distance over the grid's own steps. In each, the construction takes the generator of a pair relation rather than its expansion, and the generator is the lower level, so the spec's rule against naming compositions holds. The generalization: a construction that takes a relation over pairs of its members offers a form that takes the generator, where the generator is a value the solver already has, a score, a step, or a transform. A frame default for Ray's `node` is not one: the spec's defaults are steps, directions and the D4 identity, and the default would hide a claim.

Each row is a site not using a form the lib has, which the spec's lint rule already names: a site that writes out a cell instance the lib holds is a reimplementation.

## Derivability tests

The lower and upper bounds above are deterministic and cheap, about rows × 2^columns with early exit. The quantity that matters is conditional: the information in a table given the tables already shown, the grid and the lib. In the limit that is the shortest clause that reproduces the table from what precedes it, which is program synthesis itself. A finite version is a fixed set of derivability tests, each cheap, each with a cost for the table it derives:

- the table equals another table, or a projection of one;
- the table is the product of its projections onto a partition of its columns;
- the table is the closure of a step relation inside a node set;
- the table is a rank or a class membership written as pairs.

A table's information is the cost of the cheapest test that derives it plus its exceptions. The tests are the same forms as the compact representations, so a test that passes names what the table can be derived from.

Uses, beside the lint below: a feature for the encoder, key size, fill and bits per row per table, attached before the model attends over the rows; and a prior for synthesis, since the gold programs keep a table's information roughly proportional to its size, and a decode that produces a zero-bit table of 50,000 rows has taken a step a gold author would not.

### The lint

`uv run python -m study.table_lint [task_ids ...]` runs the tests on solvers' relations, every solver by default, and prints, for each relation over a row threshold, the test that derives it and what the test found. The principle each line states is that a table should hold something the relations it is derived from do not. It prints no line for `&output` or for a relation the decode gives no table, which `row-counts` marks with a `no table` line. Its input is the solver's rows at the stored parameters of the concept case, which `arclog-cli row-counts --rows` dumps per relation and input, and the solver's source. Each line is a row count with a finding, and the agent that rewrites the solver decides how to act on it.

| test | what passes it | what the table holds nothing beyond |
| --- | --- | --- |
| restatement | the rows equal another relation's, or a projection of one | the other relation |
| cell instance | an `edge` of Distance or Propagation whose body is the grid's adjacency inside a node set | the node set, which CellDistance or Flood takes alone |
| product | the rows are the product of the projections onto a partition of the columns; for an input, a guard with no variable times a domain | the factors; for a guard, the conjuncts that bind the columns |
| closure | the rows are the closure of a step relation inside a node set | the steps |
| order or class as pairs | the key is a pair, and the rows are the pairs some column orders, or an equivalence's pairs | a score per member; the classes |
| lib relation per pair | the rows are a lib relation, `same_line`, `neighbor`, `apply`, restricted to a cell set | the lib relation and the cell set |
| none | | a residual: the line gives the rows, the key and the bits per row |

The lines are hints. An edit of a solver is judged by its tables: `uv run python -m study.table_lint --measure <task_id>` converts the solver as committed and as its file now holds it, each apart from the corpus and cached by the solver's text, and prints each table's rows, summed over the inputs, on both sides, with the largest table, the tables over the cap and over the threshold, and whether the solver's tables got smaller. It marks a table that no relation of the solver is the source of, by the converter's name map, and it judges an edit that removes an instance of a lib component worse. An edit is kept where the solver still passes its pairs and its tables got smaller.

Where no test passes, the line is the residual class, and rewriting it takes a reading of the task; those are the briefs that need a solver session rather than an editor.

## Settled

- One table per assignment: in the encoder. Assignments are evaluated apart, since a join keeps only rows whose assignments agree, so attention across them carries nothing the program reads.
- No table per example for RULE relations: a `DET` can read a RULE's lifted form, which unions the examples, so examples cross.
- Not tables: `connected` (C20-60, and out of the lib in C20-62), one-atom instance inputs (C20-73), Connectivity.adjacent and CellDistance.predecessor (C20-76).
- The engine's projection cap stays at 10,000: at 2,000, 66 of 123 large clause relations lose a read that fits in no projection.
- The assignment cap of 256 is not a lever: no table has more than 96 assignments.
- Factorized bodies are not a lever: 98% of large-body rows are in bodies with one connected part.
- Showing an instance output only when the model asks for it, or at its first read, is not pursued: it removes whole tables and leaves each table's rows as they are.
- Projection onto read columns as a step of the language is not pursued.
